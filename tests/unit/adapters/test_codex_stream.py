"""Codex JSONL bounded chunk reader 회귀 (ADR-0033 §4)."""

import asyncio

import pytest

from mission_control.adapters.codex_stream import (
    BoundedCodexJsonlReader,
    CodexJsonlLineTooLong,
)


async def test_lines_are_reassembled_across_small_chunks() -> None:
    stream = asyncio.StreamReader()
    stream.feed_data(b'{"type":"one"}\n{"type":"two"}\n')
    stream.feed_eof()
    reader = BoundedCodexJsonlReader(stream, chunk_bytes=3, max_line_bytes=32)

    assert await reader.readline() == b'{"type":"one"}\n'
    assert await reader.readline() == b'{"type":"two"}\n'
    assert await reader.readline() == b""


async def test_a_newline_free_line_over_the_bound_fails_closed() -> None:
    stream = asyncio.StreamReader()
    stream.feed_data(b"123456789")
    stream.feed_eof()
    reader = BoundedCodexJsonlReader(stream, chunk_bytes=3, max_line_bytes=8)

    with pytest.raises(CodexJsonlLineTooLong, match="exceeded 8 bytes"):
        await reader.readline()
