# Redaction Field Trial — ADR-0040을 실물에 걸어 본 기록

> Ran: 2026-08-10. 대상:
> [ADR-0040](../adr/0040-secret-redaction-boundaries.md) (secret redaction의
> 경계와 두 프로필), 구현 `src/mission_control/security.py`.<br>
> 성격: **조사 기반 정책의 첫 실물 대조**. 정책은 upstream 조사와 합성
> 테스트만으로 세워졌고 진짜 자격증명·진짜 명령 출력에 걸어 본 적이 없었다.<br>
> Evidence level: **Measured** (이 기계의 실제 파일·실제 명령 출력).

## 0. 결론 먼저

| 방향 | 결과 |
|---|---|
| **누락** (자격증명이 새는가) | **결함 4종 발견 → 수정.** 전부 *"라벨이 붙었는데도 새는"* 것이었다 |
| **과잉** (증거가 망가지는가) | **관측 0건.** 실제 명령 출력 5종에서 한 글자도 바뀌지 않았다 |
| 정책 자체 | **유지.** ADR-0040 §1의 판단은 옳았고, 구현이 정책에 못 미쳤다 |

발견된 것은 ADR-0040 §Cost가 감수하기로 한 *"라벨 없는 미등록 형태"* 가
**아니다.** `SUPABASE_API_KEY=…`, `{"api_key": "…"}` 처럼 라벨이 가장 분명한
형태들이 새고 있었다.

## 1. 방법

값을 전사에 남기지 않기 위해 두 하네스로 나눴다.

- **하네스 A (실제 값)** — 이 기계의 설정 파일 11개를 구조 파싱해
  자격증명 계열 키의 값을 뽑고, 저장 프로필을 건 뒤 **값이 남았는지만**
  보고한다. 출력은 키 이름·값의 형태(길이·문자군)뿐이다.
  ground truth가 **키 이름**에서 나오므로 시험 대상인 정규식과 독립이다.
- **하네스 B (실제 문구)** — vendor 오류 문구는 실물 원문, 값은 같은 형태의
  합성값. 그리고 이 저장소에서 **실제로 실행한** 명령 출력 5종에 프로필을
  걸어 훼손 여부를 diff로 본다.

대상 파일: `~/.codex/config.toml`, `~/.claude.json`, `~/.gitconfig`,
`~/.npmrc`, `~/.aws/credentials`, `~/.config/gh/hosts.yml`,
`~/.docker/config.json`, 프로젝트 `.env` 2개, `.mcp.json` 2개.

## 2. 발견 — 라벨이 붙었는데도 새던 네 형태

### 2.1 `\b`가 언더스코어에서 성립하지 않는다 (근본 원인)

```
password=…              가림
DB_PASSWORD=…           **누락**
api_key=…               가림
SUPABASE_API_KEY=…      **누락**
authToken=…             가림
_authToken=…            **누락**   ← npm이 `.npmrc`·`npm ERR!`에 찍는 실제 형태
```

`_LABEL`이 `\b(?:…)\b`를 썼다. `_`는 `\w`이므로 `SUPABASE_API_KEY`의
`API_KEY` 앞에는 **단어 경계가 없다.** 환경변수 이름은 거의 전부 이 형태다.

`GITHUB_TOKEN=`이 우연히 가려지던 것이 이 결함을 가렸다 — 어휘에
`github[-_]?token`이 통째로 등록돼 있어 `\bgithub_token\b`로 매칭됐을 뿐,
경계가 동작해서가 아니다.

**upstream에는 이 문제가 없다.** `is_sensitive_field`는 경계를 쓰지 않고
**부분 문자열 포함**으로 본다 (`core/security.py:463-464`):

```python
field_lower = field_name.lower()
return any(sensitive in field_lower for sensitive in SENSITIVE_FIELD_NAMES)
```

### 2.2 이름과 구분자 사이의 따옴표 — JSON이 통째로 샜다

```
password: …             가림
{"api_key": "…"}        **누락**
{"token": "…"}          **누락**
{"auth": "…"}           **누락**
```

`_LABEL`이 이름 뒤에 `\s*[:=]`를 바로 요구했다. JSON은 이름과 `:` 사이에
닫는 따옴표가 있다.

**우리 표면에서 가장 흔한 형태다** — MCP payload, `.mcp.json`, docker
`config.json`, vendor SDK의 오류 본문이 전부 JSON이다.

### 2.3 어휘에 `key` 단독이 없었다

```
SUPABASE_SERVICE_KEY=…  **누락**
DJANGO_SECRET_KEY=…     **누락**
```

`api_key`·`private_key`·`secret_access_key`만 있고 `…_KEY` 일반형이 없었다.
upstream 어휘에는 `"key"`가 단독으로 있다 (`core/security.py:44`).

### 2.4 vendor 오류 문구의 공백 표기

OpenAI는 `Incorrect API key provided: …`라고 쓴다. `api[-_]?key`는 공백을
받지 않았다.

*(이 건은 실제로는 새지 않았다 — OpenAI 값이 `sk-`로 시작해 고신뢰 형태
규칙이 잡는다. 확인함. 그래도 어휘를 넓혔다: 다른 vendor가 같은 표기를
쓰면서 값이 접두사 없는 형태일 수 있다.)*

## 3. 수정

`security.py`:

```python
_EDGE_L = r"(?<![A-Za-z0-9])"     # `\b` 대신 — `_`를 경계로 인정한다
_EDGE_R = r"(?![A-Za-z0-9])"
_SEPARATOR = r"[\"']?\s*[:=]\s*"  # JSON의 닫는 따옴표
```

어휘에 추가: `auth`, `api[-_ ]?key`(공백), `[A-Za-z0-9]{2,}[-_]key`.

**`key` 단독은 받지 않았다.** upstream은 받지만 upstream이 보는 것은
**필드 이름**이고 우리가 훑는 것은 **산문**이다. 산문의 `the key = …`까지
지우면 증거가 사라진다. 합성 이름일 때만 받는 것이 두 목적의 절충이다.

수정 후: 라벨 형태 12/12 가려짐. 유사어(`monkey`, `author`, `oauth`,
`keyboard`, 산문의 `key`) 5/5 보존.

회귀 고정: `tests/unit/test_security.py::TestLabelledFormsFromTheFieldTrial`
(15건 추가, 전체 907 passed).

## 4. 과잉 마스킹 — 관측 0건

이 저장소에서 실제로 실행한 출력에 저장 프로필을 걸고 diff했다.

| 명령 | 출력 크기 | 변경 |
|---|---|---|
| `ruff check . --statistics` | 0자 | 없음 |
| `pytest --collect-only -q` | 8,000자 | 없음 |
| `git status --short --branch` | 107자 | 없음 |
| `git log -3 --stat` | 2,301자 | 없음 |
| `mypy src` | 0자 | 없음 |

합성 시험에서 유일하게 걸린 과잉은 `foreign_key = 3` → `foreign_key =
[redacted]`이다. **upstream도 같은 것을 지운다** — `foreign_key`는 `key`를
포함하므로 `is_sensitive_field`가 `<REDACTED>`로 만든다. 우리 쪽이 더 넓지
않으므로 divergence가 아니다.

## 5. 고치지 **않은** 것 — ADR-0040 §Cost가 실물로 확인됐다

라벨 없이 맨몸으로 나온 두 값은 여전히 통과한다:

- 64자 소문자 16진 (실제 MCP 서버 API key)
- 40자 base64 (실제 `aws_secret_access_key`)

**의도적으로 두었다.** 64자 16진은 sha256 다이제스트의 형태이고 40자 16진은
git SHA·체크섬의 형태다. 이것을 형태만으로 지우면 lock 파일·체크섬·커밋
해시가 실린 정상 출력이 전부 망가진다 — ADR-0040이 *"과잉 마스킹으로 증거를
못 읽게 만드는 쪽이 더 나쁘다"* 로 이미 판단한 자리이며, upstream도 같은
선택이다.

**단, 이 값들이 라벨과 함께 나오면(`API_KEY=…`, `{"aws_secret_access_key":
"…"}`) §3의 수정으로 이제 가려진다.** 실제 유출 경로는 거의 전부 라벨을
동반한다.

## 6. host 프로필 — 이번 대조로 판단할 수 없었다

`redact_for_host`를 실패 출력에 걸었으나, 확보한 실패 출력에 절대 경로가
포함되지 않아 경로 제거의 실물 확인이 되지 않았다. 합성 테스트는 통과한다
(`TestPathProfile`, `TestHostProfile`).

**미확인으로 남긴다.** 실물 확인은 Phase 7 MCP 응답이 실제로 나가기 시작한
뒤에나 의미가 있다 — ADR-0040 §5가 그 자리를 그때로 지정했다.

## 7. 이 대조가 남기는 교훈

정책은 옳았고 **검증 목록이 얕았다.** ADR-0040의 Verification은
`SECRET=`·`--api-key=` 같은 **가장 단순한 형태만** 적었고, 그 형태들은 전부
통과했다. 실제 세계의 형태(`SCREAMING_SNAKE=`, JSON, `.npmrc`)는 목록에
없었으므로 테스트가 초록이면서 정책이 지켜지지 않았다.

Verification 항목을 형태 목록으로 바꿔 ADR-0040에 반영했다.
