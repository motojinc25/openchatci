"""AG-UI endpoint with reasoning event support (CTR-0009, PRP-0009).

Custom AG-UI streaming endpoint that replaces add_agent_framework_fastapi_endpoint()
to emit REASONING_* events for text_reasoning content. The upstream library's
_emit_content() skips text_reasoning; this endpoint handles it directly.

Session management is enabled via FileHistoryProvider (CTR-0014).
Agent creation is delegated to agent_factory (CTR-0026, PRP-0016).
Background Responses support via CTR-0045 (PRP-0025).
"""

from collections.abc import AsyncGenerator
import json
import logging
from pathlib import Path
from typing import Any
import uuid

from ag_ui.core import (
    CustomEvent,
    EventType,
    ReasoningMessageContentEvent,
    ReasoningMessageEndEvent,
    ReasoningMessageStartEvent,
    RunErrorEvent,
    RunFinishedEvent,
    RunStartedEvent,
    TextMessageContentEvent,
    TextMessageEndEvent,
    TextMessageStartEvent,
    ToolCallArgsEvent,
    ToolCallEndEvent,
    ToolCallResultEvent,
    ToolCallStartEvent,
)
from ag_ui.encoder import EventEncoder
from agent_framework import Agent, AgentSession, Content
from agent_framework.exceptions import ChatClientException
from agent_framework_ag_ui._agent_run import _normalize_response_stream
from agent_framework_ag_ui._message_adapters import normalize_agui_input_messages
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from openai import NotFoundError as OpenAINotFoundError
from pydantic import AliasChoices, BaseModel, Field

from app.core.config import settings
from app.image_gen.tools import current_thread_id as _image_gen_thread_id

logger = logging.getLogger(__name__)


class AGUIRequest(BaseModel):
    """AG-UI protocol request (mirrors agent_framework_ag_ui._types.AGUIRequest)."""

    messages: list[dict[str, Any]] = []
    run_id: str | None = Field(default=None, validation_alias=AliasChoices("run_id", "runId"))
    thread_id: str | None = Field(default=None, validation_alias=AliasChoices("thread_id", "threadId"))
    state: dict[str, Any] | None = None
    tools: list[dict[str, Any]] | None = None
    context: list[dict[str, Any]] | None = None
    forwarded_props: dict[str, Any] | None = None


def _generate_id() -> str:
    return str(uuid.uuid4())


def _inject_image_content(
    maf_messages: list[Any],
    raw_messages: list[dict[str, Any]],
) -> None:
    """Inject image Content into MAF Messages from AG-UI request.

    The frontend sends images as ``{"images": [{"uri": "...", "media_type": "..."}]}``
    alongside the text content. ``normalize_agui_input_messages`` only handles text,
    so we resolve image references here and append to the MAF Message's contents.

    Local uploads (``/api/uploads/...``) are read from disk via ``Content.from_data()``.
    External URLs are passed via ``Content.from_uri()``.
    """
    upload_dir = Path(settings.upload_dir)
    for raw_msg in raw_messages:
        images = raw_msg.get("images")
        if not images or raw_msg.get("role") != "user":
            continue
        # Find the matching MAF user message (last user message)
        target = None
        for maf_msg in reversed(maf_messages):
            if getattr(maf_msg, "role", None) == "user":
                target = maf_msg
                break
        if target is None:
            continue
        for img in images:
            uri = img.get("uri", "")
            media_type = img.get("media_type", "")
            if uri.startswith("/api/uploads/"):
                parts = uri.split("/")  # ["", "api", "uploads", thread_id, filename]
                if len(parts) >= 5:
                    file_path = upload_dir / parts[3] / parts[4]
                    if file_path.is_file():
                        target.contents.append(Content.from_data(data=file_path.read_bytes(), media_type=media_type))
            elif uri.startswith(("http://", "https://")):
                target.contents.append(Content.from_uri(uri=uri, media_type=media_type))


async def _stream_with_reasoning(
    agent: Agent,
    request_body: AGUIRequest,
) -> AsyncGenerator[str, None]:
    """Stream AG-UI events including REASONING_* for text_reasoning content.

    Iterates the MAF agent response stream directly to emit reasoning events
    that agent-framework-ag-ui's _emit_content() would otherwise skip.
    """
    encoder = EventEncoder()
    thread_id = request_body.thread_id or _generate_id()
    run_id = request_body.run_id or _generate_id()

    yield encoder.encode(
        RunStartedEvent(
            type=EventType.RUN_STARTED,
            run_id=run_id,
            thread_id=thread_id,
        )
    )

    msg_id: str | None = None
    reasoning_msg_id: str | None = None
    tool_call_id: str | None = None
    run_error = False
    error_message = ""

    try:
        # Convert AG-UI messages to MAF Message objects
        messages, _ = normalize_agui_input_messages(request_body.messages)

        # Inject image content from request into MAF messages (CTR-0022)
        _inject_image_content(messages, request_body.messages)

        # Create session with metadata (same as _agent_run.py:685-691)
        session = AgentSession()
        session.metadata = {
            "ag_ui_thread_id": thread_id,
            "ag_ui_run_id": run_id,
        }

        # Read background options from AG-UI state (CTR-0045, PRP-0025)
        background = False
        continuation_token = None
        if request_body.state:
            background = request_body.state.get("background", False)
            continuation_token = request_body.state.get("continuation_token")

        # Validate continuation_token format: MAF expects dict with "response_id"
        if continuation_token and isinstance(continuation_token, str):
            continuation_token = {"response_id": continuation_token}

        run_options: dict[str, Any] = {}
        if background:
            run_options["background"] = True
        if continuation_token:
            run_options["continuation_token"] = continuation_token

        # Set thread_id for image generation tools (CTR-0050, PRP-0027)
        _image_gen_thread_id.set(thread_id)

        # Run agent with streaming
        response_stream = agent.run(
            messages,
            stream=True,
            session=session,
            options=run_options or None,
        )
        stream = await _normalize_response_stream(response_stream)

        async for update in stream:
            # Emit continuation_token if present (CTR-0045, PRP-0025)
            if background:
                update_ct = getattr(update, "continuation_token", None)
                if update_ct is not None:
                    yield encoder.encode(
                        CustomEvent(
                            type=EventType.CUSTOM,
                            name="continuation_token",
                            value=dict(update_ct) if hasattr(update_ct, "__iter__") else {"token": update_ct},
                        )
                    )

            contents = getattr(update, "contents", None) or []
            for content in contents:
                content_type = getattr(content, "type", None)

                if content_type == "text_reasoning":
                    text = getattr(content, "text", None)
                    if not text:
                        continue
                    if reasoning_msg_id is None:
                        reasoning_msg_id = _generate_id()
                        yield encoder.encode(
                            ReasoningMessageStartEvent(
                                type=EventType.REASONING_MESSAGE_START,
                                message_id=reasoning_msg_id,
                                role="assistant",
                            )
                        )
                    yield encoder.encode(
                        ReasoningMessageContentEvent(
                            type=EventType.REASONING_MESSAGE_CONTENT,
                            message_id=reasoning_msg_id,
                            delta=text,
                        )
                    )

                elif content_type == "text":
                    text = getattr(content, "text", None)
                    if not text:
                        continue
                    # Close any open reasoning block before text
                    if reasoning_msg_id is not None:
                        yield encoder.encode(
                            ReasoningMessageEndEvent(
                                type=EventType.REASONING_MESSAGE_END,
                                message_id=reasoning_msg_id,
                            )
                        )
                        reasoning_msg_id = None
                    if msg_id is None:
                        msg_id = _generate_id()
                        yield encoder.encode(
                            TextMessageStartEvent(
                                type=EventType.TEXT_MESSAGE_START,
                                message_id=msg_id,
                                role="assistant",
                            )
                        )
                    yield encoder.encode(
                        TextMessageContentEvent(
                            type=EventType.TEXT_MESSAGE_CONTENT,
                            message_id=msg_id,
                            delta=text,
                        )
                    )

                elif content_type == "function_call":
                    # Close reasoning block before tool call
                    if reasoning_msg_id is not None:
                        yield encoder.encode(
                            ReasoningMessageEndEvent(
                                type=EventType.REASONING_MESSAGE_END,
                                message_id=reasoning_msg_id,
                            )
                        )
                        reasoning_msg_id = None

                    tc_id = getattr(content, "call_id", None) or _generate_id()
                    tc_name = getattr(content, "name", None)
                    if tc_name and tc_id != tool_call_id:
                        tool_call_id = tc_id
                        yield encoder.encode(
                            ToolCallStartEvent(
                                type=EventType.TOOL_CALL_START,
                                tool_call_id=tc_id,
                                tool_call_name=tc_name,
                                parent_message_id=msg_id,
                            )
                        )
                    tc_args = getattr(content, "arguments", None)
                    if tc_args:
                        delta = tc_args if isinstance(tc_args, str) else json.dumps(tc_args)
                        yield encoder.encode(
                            ToolCallArgsEvent(
                                type=EventType.TOOL_CALL_ARGS,
                                tool_call_id=tc_id,
                                delta=delta,
                            )
                        )

                elif content_type == "function_result":
                    tc_id = getattr(content, "call_id", None)
                    if tc_id:
                        yield encoder.encode(
                            ToolCallEndEvent(
                                type=EventType.TOOL_CALL_END,
                                tool_call_id=tc_id,
                            )
                        )
                        raw_result = getattr(content, "result", "") or ""
                        result_str = raw_result if isinstance(raw_result, str) else json.dumps(raw_result)
                        yield encoder.encode(
                            ToolCallResultEvent(
                                type=EventType.TOOL_CALL_RESULT,
                                message_id=_generate_id(),
                                tool_call_id=tc_id,
                                content=result_str,
                                role="tool",
                            )
                        )
                        tool_call_id = None
                        # Reset text message after tool result (allows new text block)
                        if msg_id is not None:
                            yield encoder.encode(
                                TextMessageEndEvent(
                                    type=EventType.TEXT_MESSAGE_END,
                                    message_id=msg_id,
                                )
                            )
                            msg_id = None

                elif content_type == "usage":
                    usage_details = getattr(content, "usage_details", None) or {}
                    usage_value = dict(usage_details)
                    usage_value["max_context_tokens"] = settings.model_max_context_tokens
                    yield encoder.encode(
                        CustomEvent(
                            type=EventType.CUSTOM,
                            name="usage",
                            value=usage_value,
                        )
                    )

    except (OpenAINotFoundError, ChatClientException, TypeError) as exc:
        run_error = True
        if continuation_token:
            error_message = "Background response token not found or expired. Please resend your message."
            logger.warning("Continuation token error for thread %s: %s", thread_id, exc)
        else:
            error_message = "An internal error occurred during agent execution."
            logger.exception("AG-UI stream error")

    except Exception:
        run_error = True
        if continuation_token:
            error_message = "Background response token not found or expired. Please resend your message."
            logger.warning("Continuation token error for thread %s", thread_id, exc_info=True)
        else:
            error_message = "An internal error occurred during agent execution."
            logger.exception("AG-UI stream error")

    # Always finalize open blocks -- even after exceptions, so the frontend
    # can stop thinking indicators and display any error.
    if reasoning_msg_id is not None:
        yield encoder.encode(
            ReasoningMessageEndEvent(
                type=EventType.REASONING_MESSAGE_END,
                message_id=reasoning_msg_id,
            )
        )
    if msg_id is not None:
        yield encoder.encode(
            TextMessageEndEvent(
                type=EventType.TEXT_MESSAGE_END,
                message_id=msg_id,
            )
        )

    if run_error:
        yield encoder.encode(
            RunErrorEvent(
                type=EventType.RUN_ERROR,
                message=error_message,
            )
        )
    yield encoder.encode(
        RunFinishedEvent(
            type=EventType.RUN_FINISHED,
            run_id=run_id,
            thread_id=thread_id,
        )
    )


def register_agui_endpoints(app: FastAPI, *, agent: Agent) -> None:
    """Register custom AG-UI endpoint with reasoning support (CTR-0009).

    Replaces add_agent_framework_fastapi_endpoint() to handle text_reasoning
    content that the upstream library skips. CORS is handled at app level.
    Agent instance is created by agent_factory (CTR-0026).
    """

    @app.post("/ag-ui/", tags=["AG-UI"])
    async def agui_endpoint(request_body: AGUIRequest):
        return StreamingResponse(
            _stream_with_reasoning(agent, request_body),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    logger.info("AG-UI endpoint registered at /ag-ui/ (reasoning + session management enabled)")
