"""Unit tests for :mod:`backend.knowledge.documents.checksum`.

Covers determinism, stability across multiple reads, distinct digests for
distinct bytes, and the empty-file edge case — the invariants the
deduplication logic depends on.
"""
from backend.knowledge.documents.checksum import (
    compute_bytes_checksum,
    compute_file_checksum,
)


class TestCompute:
    def test_bytes_checksum_is_deterministic(self):
        a = compute_bytes_checksum(b"hello world")
        b = compute_bytes_checksum(b"hello world")
        assert a == b
        assert len(a) == 64

    def test_bytes_checksum_distinguishes_inputs(self):
        assert compute_bytes_checksum(b"hello") != compute_bytes_checksum(b"hello!")

    def test_file_checksum_matches_bytes_checksum(self, tmp_path):
        payload = b"some PDF-like bytes\n" * 1024
        f = tmp_path / "sample.bin"
        f.write_bytes(payload)
        assert compute_file_checksum(f) == compute_bytes_checksum(payload)

    def test_file_checksum_stable_across_reads(self, tmp_path):
        f = tmp_path / "sample.bin"
        f.write_bytes(b"x" * 200_000)
        first = compute_file_checksum(f)
        second = compute_file_checksum(f)
        assert first == second

    def test_file_checksum_handles_empty_file(self, tmp_path):
        f = tmp_path / "empty.bin"
        f.write_bytes(b"")
        assert compute_file_checksum(f) == compute_bytes_checksum(b"")
