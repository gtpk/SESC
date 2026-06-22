from __future__ import annotations

from pathlib import Path

import pytest

from ism.data.generator import SyntheticGenerator
from ism.data.io import read_documents, write_documents


def test_p1_io_002_export_import_preserves_documents(tmp_path: Path) -> None:
    path = tmp_path / "documents.jsonl"
    documents = SyntheticGenerator(42).generate(10)

    write_documents(path, documents)
    restored = read_documents(path)

    assert restored == documents


def test_p1_io_001_corrupt_jsonl_reports_line_number(tmp_path: Path) -> None:
    path = tmp_path / "corrupt.jsonl"
    path.write_text('{"valid": true}\n{not-json}\n', encoding="utf-8")

    with pytest.raises(ValueError, match=r"corrupt\.jsonl:2: invalid JSON"):
        read_documents(path)


def test_writer_replaces_existing_file_atomically(tmp_path: Path) -> None:
    path = tmp_path / "documents.jsonl"
    first = SyntheticGenerator(1).generate(2)
    second = SyntheticGenerator(2).generate(3)

    write_documents(path, first)
    write_documents(path, second)

    assert read_documents(path) == second
