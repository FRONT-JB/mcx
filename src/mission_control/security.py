"""노출 경계의 redaction 정책 (ADR-0040).

프로필은 **둘**이고 섞으면 안 된다.

``redact_credentials``  — **저장 프로필.** 자격증명만 가린다. 상태 문서에
들어가는 발췌(`output_tail`, attempt `error`)에 걸린다. 경로를 남기는 이유는
그 발췌가 Recover를 거쳐 **worker에게 전달**되기 때문이다 — 어느 파일이
실패했는지 모르는 worker는 같은 실패를 반복한다.

``redact_for_host``  — **host 프로필.** 자격증명에 더해 로컬 경로를 가리고,
원시 출력 본문은 애초에 싣지 않는다(참조만). host 대화로 나가는 payload에
걸린다 — Phase 7 MCP 응답이 그 자리다.

``is_replay_unsafe``  — **저장 거부.** 원장처럼 lifecycle 성격의 기록은
프롬프트·원시 출력을 아예 담지 못한다. 마스킹이 아니라 거부다: 무엇이 들어올지도
크기도 통제되지 않는 값은 그 자리에 있으면 안 된다.

upstream은 이 셋을 서로 다른 코드로 둔다 — 입력 한도(`core/security.py`),
로깅(`observability/logging.py`), 저장 거부(`orchestrator/workflow_lifecycle.py`),
MCP 출력 마스킹(`mcp/resources/handlers.py`). 근거는
``docs/research/SECURITY_UPSTREAM_FINDINGS.md``.
"""

from __future__ import annotations

from collections.abc import Mapping
import re
from typing import Any

from mission_control.domain.errors import MissionControlError

#: 가려진 자리에 남기는 표식. 값의 길이를 유추할 수 없어야 한다.
REDACTED = "[redacted]"

#: 경로가 지워진 자리. 자격증명과 구분해야 원인 분석이 가능하다.
REDACTED_PATH = "[redacted path]"

#: lifecycle 기록이 담을 수 없는 키 (upstream ``_REPLAY_UNSAFE_KEYS`` 정렬).
#: 자격증명만이 아니라 프롬프트·원시 출력이 같은 등급이다 — replay-unsafe.
REPLAY_UNSAFE_KEYS: frozenset[str] = frozenset(
    {
        "api_key",
        "apikey",
        "auth_token",
        "bearer_token",
        "client_secret",
        "credential",
        "credentials",
        "password",
        "private_key",
        "prompt",
        "raw_output",
        "raw_prompt",
        "raw_stderr",
        "raw_stdout",
        "refresh_token",
        "secret",
        "stderr",
        "stdout",
        "token",
    }
)

#: 접미사 규칙 — ``worker_prompt``·``verify_stdout`` 같은 합성 이름을 잡는다.
REPLAY_UNSAFE_SUFFIXES: tuple[str, ...] = (
    "_api_key",
    "_credential",
    "_credentials",
    "_password",
    "_prompt",
    "_secret",
    "_stderr",
    "_stdout",
    "_token",
)

#: 값 전체를 지워야 하는 필드명의 마지막 조각.
_SECRET_FIELD_TAILS: frozenset[str] = frozenset(
    {"credential", "credentials", "key", "password", "secret", "token"}
)

_SECRET_WORD = (
    r"api[-_]?key"
    r"|(?:access|auth|bearer|github|gh|refresh)[-_]?token"
    r"|token"
    r"|password"
    r"|(?:client[-_]?)?secret"
    r"|credentials?"
    r"|private[-_]?key"
    r"|(?:aws[-_])?secret[-_]access[-_]key"
    r"|authorization"
)

#: ``--api-key=X`` / ``--token X`` — 명령줄에 실린 값.
_FLAG = re.compile(rf"(?i)(--(?:{_SECRET_WORD})(?:=|\s+))(\"[^\"]*\"|'[^']*'|[^\s,;]+)")

#: ``api_key: X`` / ``SECRET=X`` — 라벨이 붙은 값.
_LABEL = re.compile(rf"(?i)(\b(?:{_SECRET_WORD})\b\s*[:=]\s*)(\"[^\"]*\"|'[^']*'|[^,;\n]+)")

_BEARER = re.compile(r"(?i)\bBearer\s+[^\s,;]+")

#: 라벨이 없어도 형태만으로 자격증명이라고 볼 수 있는 것만 지운다. 과잉
#: 마스킹은 증거를 못 읽게 만들므로 고신뢰 형태로 좁힌다.
_HIGH_CONFIDENCE = re.compile(
    r"\b(?:"
    r"gh[pousr]_[A-Za-z0-9_]{20,}"
    r"|github_pat_[A-Za-z0-9_]{20,}"
    r"|sk-[A-Za-z0-9][A-Za-z0-9_-]{8,}"
    r"|xox[bpa]-[A-Za-z0-9-]{10,}"
    r"|glpat-[A-Za-z0-9_-]{16,}"
    # 길이를 상한 없이 둔다 — 한 글자 길다고 통째로 놓치는 것보다 낫다.
    r"|AIza[A-Za-z0-9_-]{35,}"
    r"|A[KS]IA[0-9A-Z]{16}"
    r"|[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}"
    r")\b"
)

_URL = re.compile(r"https?://[^\s,;:'\")\]}]+")
_WINDOWS_PATH = re.compile(r"\b[A-Za-z]:\\[^\s,;'\"\]}]*")
#: ``~/…``와 절대경로. 앞에 경계가 있어야 ``a/b`` 같은 상대경로를 안 건드린다.
_POSIX_PATH = re.compile(r"(^|[\s,;:='\"`(<{\[])(~[/\\][^\s,;'\"\]}]*|/[^\s,;'\"\]}]+)")


class RedactionError(MissionControlError):
    """lifecycle 기록이 담을 수 없는 값을 담으려 했다.

    마스킹으로 구제하지 않는다 — 그 자리에 있으면 안 되는 값이다.
    """


def is_replay_unsafe(key: str) -> bool:
    """이 키가 lifecycle 기록에 들어갈 수 없는가."""
    normalized = key.strip().lower()
    return normalized in REPLAY_UNSAFE_KEYS or normalized.endswith(REPLAY_UNSAFE_SUFFIXES)


def reject_replay_unsafe(payload: Mapping[str, Any], *, where: str) -> None:
    """중첩된 payload 전체에서 replay-unsafe 키를 찾아 거부한다.

    Raises:
        RedactionError: 하나라도 있으면. 어느 키인지 이름으로 알린다.
    """
    for key in _all_keys(payload):
        if is_replay_unsafe(key):
            raise RedactionError(f"{where}는 replay-unsafe 키 `{key}`를 담을 수 없다")


def _all_keys(value: Any) -> list[str]:
    if isinstance(value, Mapping):
        keys: list[str] = []
        for key, item in value.items():
            keys.append(str(key))
            keys.extend(_all_keys(item))
        return keys
    if isinstance(value, (list, tuple)):
        return [key for item in value for key in _all_keys(item)]
    return []


def redact_credentials(text: str) -> str:
    """자격증명만 가린다 — 저장 프로필. 경로와 그 밖의 본문은 그대로다."""
    if not text:
        return text
    masked = _FLAG.sub(lambda match: f"{match.group(1)}{REDACTED}", text)
    masked = _LABEL.sub(lambda match: f"{match.group(1)}{REDACTED}", masked)
    masked = _BEARER.sub(f"Bearer {REDACTED}", masked)
    return _HIGH_CONFIDENCE.sub(REDACTED, masked)


def redact_paths(text: str) -> str:
    """로컬 경로를 가린다. URL은 경로처럼 생겼어도 보존한다."""
    if not text:
        return text
    urls: list[str] = []

    def hold(match: re.Match[str]) -> str:
        urls.append(match.group(0))
        return f"\x00url{len(urls) - 1}\x00"

    held = _URL.sub(hold, text)
    held = _WINDOWS_PATH.sub(REDACTED_PATH, held)
    held = _POSIX_PATH.sub(lambda match: f"{match.group(1)}{REDACTED_PATH}", held)
    for index, url in enumerate(urls):
        held = held.replace(f"\x00url{index}\x00", url)
    return held


def redact_for_host(value: Any) -> Any:
    """host 대화로 나가는 payload를 가린다 — 자격증명 + 로컬 경로.

    민감한 이름의 필드는 값 전체를 지운다. 나머지 문자열은 패턴으로만 가려
    증거를 읽을 수 있게 남긴다. dict·list를 재귀적으로 내려간다.
    """
    return _walk(value, key=None)


def _walk(value: Any, *, key: str | None) -> Any:
    if key is not None and _is_secret_field(key):
        return REDACTED
    if isinstance(value, Mapping):
        return {str(name): _walk(item, key=str(name)) for name, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_walk(item, key=None) for item in value]
    if isinstance(value, str):
        return redact_paths(redact_credentials(value))
    return value


def _is_secret_field(name: str) -> bool:
    parts = [part for part in re.split(r"[^a-z0-9]+", name.strip().lower()) if part]
    if not parts:
        return False
    if name.strip().lower() in REPLAY_UNSAFE_KEYS:
        return True
    return parts[-1] in _SECRET_FIELD_TAILS
