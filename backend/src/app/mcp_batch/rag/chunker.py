"""Overlap-based text chunking for RAG pipeline (CTR-0076, PRP-0037).

Splits text into overlapping chunks for embedding.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def chunk_text(
    text: str,
    chunk_size: int = 800,
    chunk_overlap: int = 200,
) -> list[str]:
    """Split text into overlapping chunks by character count.

    Args:
        text: Input text to chunk.
        chunk_size: Maximum characters per chunk.
        chunk_overlap: Overlap characters between consecutive chunks.

    Returns:
        List of non-empty text chunks.
    """
    if not text or not text.strip():
        return []

    if chunk_size <= 0:
        chunk_size = 800
    if chunk_overlap < 0 or chunk_overlap >= chunk_size:
        chunk_overlap = min(200, chunk_size // 4)

    chunks: list[str] = []
    start = 0
    text_len = len(text)

    while start < text_len:
        end = start + chunk_size
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        # Advance by (chunk_size - overlap) to create overlapping windows
        start += chunk_size - chunk_overlap

    return chunks


def chunk_pages(
    pages: list[dict],
    chunk_size: int = 800,
    chunk_overlap: int = 200,
) -> list[dict]:
    """Chunk all pages and produce records with metadata.

    Args:
        pages: List of page dicts from pdf_parser.extract_pages().
        chunk_size: Characters per chunk.
        chunk_overlap: Overlap between chunks.

    Returns:
        List of dicts with keys: text, source, page, chunk_index, chunk_id.
    """
    records: list[dict] = []
    for page_info in pages:
        text = page_info["text"]
        source = page_info["source"]
        page = page_info["page"]

        chunks = chunk_text(text, chunk_size, chunk_overlap)
        for idx, chunk in enumerate(chunks):
            chunk_id = f"{source}__p{page}__c{idx}"
            records.append(
                {
                    "text": chunk,
                    "source": source,
                    "page": page,
                    "chunk_index": idx,
                    "chunk_id": chunk_id,
                }
            )

    logger.info(
        "Chunked %d pages into %d chunks (size=%d, overlap=%d)", len(pages), len(records), chunk_size, chunk_overlap
    )
    return records
