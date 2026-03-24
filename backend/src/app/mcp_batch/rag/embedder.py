"""Azure OpenAI Embedding wrapper for RAG pipeline (CTR-0076, PRP-0037).

Embeds text chunks in batches using the Azure OpenAI Embedding API.
"""

from __future__ import annotations

import logging
import os

from azure.identity import AzureCliCredential, get_bearer_token_provider
from openai import AzureOpenAI

logger = logging.getLogger(__name__)

# Azure OpenAI Embedding API accepts up to 2048 inputs per request,
# but practical batch size is kept at 100 for progress granularity.
EMBEDDING_BATCH_SIZE = 100


def _create_client() -> AzureOpenAI:
    """Create Azure OpenAI client using Azure CLI credentials."""
    endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT", "")
    if not endpoint:
        msg = "AZURE_OPENAI_ENDPOINT must be set for RAG embedding"
        raise ValueError(msg)

    token_provider = get_bearer_token_provider(
        AzureCliCredential(),
        "https://cognitiveservices.azure.com/.default",
    )
    return AzureOpenAI(
        azure_ad_token_provider=token_provider,
        azure_endpoint=endpoint,
        api_version="2024-10-21",
    )


def embed_texts(texts: list[str], model: str | None = None) -> list[list[float]]:
    """Embed a list of texts using Azure OpenAI Embedding API.

    Args:
        texts: Texts to embed.
        model: Deployment name (default: EMBEDDING_DEPLOYMENT_NAME env var).

    Returns:
        List of embedding vectors (same order as input texts).
    """
    if not texts:
        return []

    deployment = model or os.environ.get("EMBEDDING_DEPLOYMENT_NAME", "text-embedding-3-small")
    client = _create_client()

    response = client.embeddings.create(
        input=texts,
        model=deployment,
    )

    embeddings = [item.embedding for item in response.data]
    logger.info("Embedded %d texts via %s", len(embeddings), deployment)
    return embeddings


def embed_texts_batched(
    texts: list[str],
    batch_size: int = EMBEDDING_BATCH_SIZE,
    model: str | None = None,
) -> list[list[float]]:
    """Embed texts in batches to handle large document sets.

    Args:
        texts: All texts to embed.
        batch_size: Number of texts per API call.
        model: Deployment name.

    Returns:
        List of all embedding vectors.
    """
    all_embeddings: list[list[float]] = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        embeddings = embed_texts(batch, model)
        all_embeddings.extend(embeddings)
    return all_embeddings
