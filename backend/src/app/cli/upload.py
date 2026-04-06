"""CLI Upload Subcommand (CTR-0082, PRP-0041).

Provides file upload to sessions via REST API (CTR-0022).
"""

from __future__ import annotations

import mimetypes
from pathlib import Path
import sys
from typing import TYPE_CHECKING

from app.cli.client import client_from_args, output_json

if TYPE_CHECKING:
    import argparse
    from collections.abc import Callable


def register_upload_parser(
    subparsers: argparse._SubParsersAction,
    add_client_options: Callable[[argparse.ArgumentParser], None],
) -> None:
    """Register the 'upload' subcommand parser."""
    upload_parser = subparsers.add_parser("upload", help="Upload file to session")
    add_client_options(upload_parser)
    upload_parser.add_argument("file", help="File path to upload")
    upload_parser.add_argument("-s", "--session", required=True, help="Target session/thread ID")
    upload_parser.set_defaults(func=_run_upload)


def _run_upload(args: argparse.Namespace) -> None:
    file_path = Path(args.file)
    if not file_path.is_file():
        print(f"Error: File '{args.file}' not found.", file=sys.stderr)
        sys.exit(1)

    content_type = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"

    client = client_from_args(args)
    try:
        with file_path.open("rb") as f:
            response = client.post(
                f"/api/upload/{args.session}",
                files={"file": (file_path.name, f, content_type)},
            )
        data = response.json()

        if args.json_output:
            output_json(data)
        else:
            print(f"Uploaded {data.get('filename', file_path.name)} to session {args.session}")
            print(f"URI: {data.get('uri', '')}")
    finally:
        client.close()
