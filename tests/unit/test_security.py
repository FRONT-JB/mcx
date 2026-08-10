"""노출 경계의 redaction (ADR-0040).

프로필 둘의 차이가 이 파일의 핵심이다 — 저장 프로필은 경로를 남기고 host
프로필은 지운다. 섞이면 worker가 실패 원인을 못 읽거나(경로 소실), host가
로컬 구조를 본다.
"""

import pytest

from mission_control.security import (
    REDACTED,
    REDACTED_PATH,
    RedactionError,
    is_replay_unsafe,
    redact_credentials,
    redact_for_host,
    redact_paths,
    reject_replay_unsafe,
)


class TestCredentialProfile:
    @pytest.mark.parametrize(
        "secret",
        [
            "ghp_abcdefghijklmnopqrstuvwxyz0123",
            "sk-ant-api03-AbCdEfGhIjKlMnOp",
            "AIzaSyA1234567890abcdefghijklmnopqrstuvw",
            "AKIAIOSFODNN7EXAMPLE",
            "xoxb-1234567890-abcdefghij",
            "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.SflKxwRJSMeKKF2QT4f",
        ],
    )
    def test_high_confidence_shapes_are_removed(self, secret: str) -> None:
        assert secret not in redact_credentials(f"failed with token {secret} in call")

    def test_a_flag_value_is_removed(self) -> None:
        masked = redact_credentials("curl --api-key=hunter2 https://example.com")

        assert "hunter2" not in masked
        assert REDACTED in masked

    def test_a_labelled_value_is_removed(self) -> None:
        assert "s3cr3t" not in redact_credentials("AWS_SECRET_ACCESS_KEY=s3cr3t")

    def test_a_bearer_value_is_removed(self) -> None:
        assert "abc.def" not in redact_credentials("Authorization: Bearer abc.def")

    def test_ordinary_text_is_untouched(self) -> None:
        """과잉 마스킹은 증거를 못 읽게 만든다 — 고신뢰 형태만 지운다."""
        text = "AssertionError: expected 3 items, got 2 (tests/test_x.py:41)"

        assert redact_credentials(text) == text

    def test_paths_survive_the_storage_profile(self) -> None:
        """이 발췌는 worker에게 간다 — 어느 파일이 실패했는지 지우면 안 된다."""
        text = "FileNotFoundError: /Users/jb/project/src/app.py"

        assert redact_credentials(text) == text


class TestLabelledFormsFromTheFieldTrial:
    """실물 대조가 잡은 누락 (``docs/research/REDACTION_FIELD_TRIAL.md``).

    전부 **라벨이 붙은** 형태다 — ADR-0040 §1이 가리기로 한 것이며 ADR이
    감수하기로 한 "라벨 없는 미등록 형태"가 아니다. 원인은 둘이었다:
    ``\\b``가 언더스코어에서 성립하지 않는 것과, 이름과 구분자 사이의 따옴표.
    """

    SECRET = "a1b2c3d4e5f60718293a4b5c6d7e8f90"

    @pytest.mark.parametrize(
        ("label", "template"),
        [
            # 언더스코어가 앞에 붙으면 `\b`가 성립하지 않던 자리
            ("환경변수 password", "DB_PASSWORD={secret}"),
            ("환경변수 api_key", "SUPABASE_API_KEY={secret}"),
            ("환경변수 token", "GITHUB_TOKEN={secret}"),
            ("npm 원문", "//registry.npmjs.org/:_authToken={secret}"),
            # `key` 단독은 어휘에 없어 합성 이름이 통과하던 자리
            ("SERVICE_KEY", "SUPABASE_SERVICE_KEY={secret}"),
            ("SECRET_KEY", "DJANGO_SECRET_KEY={secret}"),
            # 이름과 구분자 사이의 닫는 따옴표
            ("JSON api_key", '{{"api_key": "{secret}"}}'),
            ("JSON token", '{{"token": "{secret}"}}'),
            ("docker auth", '{{"auth": "{secret}"}}'),
            # vendor 오류 문구의 공백 표기
            ("공백 API key", "Invalid API key = {secret}"),
        ],
    )
    def test_a_labelled_credential_is_removed(self, label: str, template: str) -> None:
        text = template.format(secret=self.SECRET)

        assert self.SECRET not in redact_credentials(text), label

    @pytest.mark.parametrize(
        "text",
        [
            "the key = value here",
            "author = Jane Doe",
            "oauth flow = pkce",
            "monkey = banana",
            "keyboard = qwerty",
        ],
    )
    def test_lookalike_words_do_not_trigger(self, text: str) -> None:
        """경계를 넓힌 대가로 산문이 지워지면 안 된다."""
        assert redact_credentials(text) == text


class TestPathProfile:
    def test_absolute_and_home_paths_are_removed(self) -> None:
        masked = redact_paths("no such file: /Users/jb/secret/app.py and ~/notes.md")

        assert "/Users/jb" not in masked
        assert "~/notes.md" not in masked
        assert masked.count(REDACTED_PATH) == 2

    def test_a_windows_path_is_removed(self) -> None:
        assert "C:\\Users" not in redact_paths(r"cannot open C:\Users\jb\app.py")

    def test_a_url_survives(self) -> None:
        """URL은 경로처럼 생겼지만 로컬 구조를 드러내지 않는다."""
        text = "posted to https://api.example.com/v1/runs/42"

        assert redact_paths(text) == text

    def test_a_relative_path_survives(self) -> None:
        text = "see tests/unit/test_x.py for the case"

        assert redact_paths(text) == text


class TestHostProfile:
    def test_it_removes_both_credentials_and_paths(self) -> None:
        masked = redact_for_host("wrote sk-ant-api03-AbCdEfGhIjKl to /Users/jb/.env")

        assert "sk-ant" not in masked
        assert "/Users/jb" not in masked

    def test_a_secret_field_name_removes_the_whole_value(self) -> None:
        """이름이 비밀이라고 말하면 형태를 보지 않는다."""
        masked = redact_for_host({"api_key": "plainlookingvalue", "note": "ok"})

        assert masked == {"api_key": REDACTED, "note": "ok"}

    def test_it_walks_nested_structures(self) -> None:
        masked = redact_for_host({"runs": [{"output_tail": "token: abc123xyz"}]})

        assert "abc123xyz" not in masked["runs"][0]["output_tail"]

    def test_non_strings_pass_through(self) -> None:
        assert redact_for_host({"exit_code": 2, "passed": False, "ref": None}) == {
            "exit_code": 2,
            "passed": False,
            "ref": None,
        }


class TestReplayUnsafeKeys:
    @pytest.mark.parametrize(
        "key", ["stdout", "stderr", "prompt", "raw_output", "api_key", "password"]
    )
    def test_the_blocklist_covers_more_than_credentials(self, key: str) -> None:
        """프롬프트·원시 출력은 자격증명과 같은 등급이다 — 무엇이 들어올지 통제되지 않는다."""
        assert is_replay_unsafe(key)

    @pytest.mark.parametrize("key", ["worker_prompt", "verify_stdout", "vendor_api_key"])
    def test_compound_names_are_caught_by_suffix(self, key: str) -> None:
        assert is_replay_unsafe(key)

    @pytest.mark.parametrize("key", ["command", "exit_code", "calls", "duration_seconds"])
    def test_ordinary_keys_pass(self, key: str) -> None:
        assert not is_replay_unsafe(key)

    def test_rejection_names_the_offending_key(self) -> None:
        with pytest.raises(RedactionError) as caught:
            reject_replay_unsafe({"event": "end", "raw_stdout": "..."}, where="원장")
        assert "raw_stdout" in str(caught.value)

    def test_rejection_reaches_nested_values(self) -> None:
        with pytest.raises(RedactionError):
            reject_replay_unsafe({"details": [{"prompt": "..."}]}, where="원장")


class TestDottedIdentifiersSurvive:
    """도그푸딩 0005 §3 — 실사용에서 처음 관측된 과잉 마스킹.

    JWT 형태(세 조각 점 구분, 각 8자 이상)가 평범한 파이썬 점 표기를 잡았다.
    upstream의 같은 패턴은 **필드 값**에 걸리고 우리는 산문을 훑는다 — 그래서
    라벨 없는 층에서는 실제 JWT의 `eyJ` 접두사를 요구한다.
    """

    @pytest.mark.parametrize(
        "text",
        [
            "unittest.defaultTestLoader.loadTestsFromModule(test_roman)",
            "concurrent.futures.ProcessPoolExecutor",
            "importlib.metadata.PackageNotFoundError",
        ],
    )
    def test_a_dotted_identifier_is_not_a_credential(self, text: str) -> None:
        assert redact_credentials(text) == text

    def test_a_real_jwt_is_still_removed_without_a_label(self) -> None:
        token = (
            "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0."
            "dBjftJeZ4CVPmB92K27uhbUJU1p1r_wW1gFWFOEjXk"
        )

        assert token not in redact_credentials(f"request failed with {token} in header")

    def test_a_labelled_token_does_not_need_the_prefix(self) -> None:
        """접두사 요구는 라벨 없는 층에만 걸린다."""
        opaque = "abcdefgh.ijklmnopq.rstuvwxyz"

        assert opaque not in redact_credentials(f"api_key={opaque}")
