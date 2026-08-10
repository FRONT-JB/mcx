"""Codex CLI의 큰 JSONL event를 bounded chunk로 읽는다.

Codex는 asyncio ``StreamReader`` 기본 64 KiB보다 큰 event 한 줄을 낼 수 있다.
따라서 ``readline()``에 의존하지 않고 fixed-size chunk를 조립한다. newline 없는
출력은 pinned Ouroboros와 같은 50 MiB에서 실패로 닫는다
(``RUNTIME_UPSTREAM_FINDINGS.md`` §8.1).
"""

from __future__ import annotations

import asyncio

CODEX_STREAM_CHUNK_BYTES = 16 * 1024
MAX_CODEX_JSONL_LINE_BYTES = 50 * 1024 * 1024


class CodexJsonlLineTooLong(RuntimeError):
    """Codex stdout 한 줄이 bounded buffer 계약을 넘었다."""


class BoundedCodexJsonlReader:
    """``StreamReader.readline``의 64 KiB 암묵 제한 없는 bounded line reader."""

    def __init__(
        self,
        stream: asyncio.StreamReader,
        *,
        chunk_bytes: int = CODEX_STREAM_CHUNK_BYTES,
        max_line_bytes: int = MAX_CODEX_JSONL_LINE_BYTES,
    ) -> None:
        self._stream = stream
        self._chunk_bytes = chunk_bytes
        self._max_line_bytes = max_line_bytes
        self._buffer = bytearray()
        self._eof = False

    async def readline(self) -> bytes:
        """다음 한 줄을 반환한다. newline은 보존하고 EOF 뒤에는 ``b""``다."""
        while True:
            newline = self._buffer.find(b"\n")
            if newline >= 0:
                if newline > self._max_line_bytes:
                    self._raise_too_long()
                end = newline + 1
                line = bytes(self._buffer[:end])
                del self._buffer[:end]
                return line

            if len(self._buffer) > self._max_line_bytes:
                self._raise_too_long()

            if self._eof:
                if not self._buffer:
                    return b""
                line = bytes(self._buffer)
                self._buffer.clear()
                return line

            chunk = await self._stream.read(self._chunk_bytes)
            if chunk:
                self._buffer.extend(chunk)
            else:
                self._eof = True

    def _raise_too_long(self) -> None:
        raise CodexJsonlLineTooLong(
            f"Codex JSONL line exceeded {self._max_line_bytes} bytes"
        )
