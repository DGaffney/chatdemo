"""SHA-256 checksums for document identity + deduplication.

Documents are keyed by the SHA-256 of their file bytes, so re-processing
the same PDF is a no-op and re-uploading an edited version produces a
distinct row that can supersede the old one. File checksums are streamed
in 64 KiB blocks so multi-megabyte PDFs don't balloon memory.
"""
import hashlib
from pathlib import Path


def compute_file_checksum(file_path: str | Path, chunk_size: int = 65536) -> str:
    """Return the SHA-256 hex digest of a file's bytes.

    Streams the file in chunks so large PDFs don't blow up memory.
    """
    sha = hashlib.sha256()
    with open(file_path, "rb") as f:
        for block in iter(lambda: f.read(chunk_size), b""):
            sha.update(block)
    return sha.hexdigest()


def compute_bytes_checksum(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
