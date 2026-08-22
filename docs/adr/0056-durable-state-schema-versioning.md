# ADR 0056 — durable state JSON 문서에 명시적 schema version과 미지 필드 거부를 둔다

- Status: Accepted
- Date: 2026-08-23
- Constitutional basis: §7 Evidence over reasoning, §17 Scope와 Reasoning
  Discipline, [ADR-0005](./0005-evidence-over-reasoning.md)
- Related issue: [#3](https://github.com/FRONT-JB/mcx/issues/3)
- Upstream baseline: `Q00/ouroboros@9486c78575a0332e9b84d93ef5832985291d7943`

## Context

Mission Control의 다섯 durable JSON 문서(`BriefState`, `BlueprintState`,
`ExecuteState`, `VerifyState`, `MissionRecord`)는 문서 형식을 식별하는 필드가
없고, Pydantic의 기본 `extra="ignore"` 동작으로 최상위 미지 필드를 조용히
버린다. 따라서 현재 코드에 없는 필드를 가진 문서를 성공적으로 읽은 뒤 다시
저장하면 그 필드가 사라진다.

예를 들어 다음 문서는 현재 로드에 성공하지만 round-trip 뒤
`schema_version`과 `unknown_field`가 모두 없어질 수 있다.

```json
{
  "schema_version": 99,
  "unknown_field": true,
  "mission_id": "m-1"
}
```

이 동작은 손상되거나 미래 버전인 durable state를 정상 상태로 오인하게 한다.
특히 저장소 adapter는 raw JSON을 각 모델의 `model_validate_json`에 바로 넘기므로,
이 경계에서 알 수 없는 문서를 멈추는 것이 가장 좁은 수정이다.

## Upstream comparison

고정 baseline의 `bigbang/interview.py`는 파일을 읽은 뒤 다음과 같이 직접 모델을
검증한다.

```python
state = InterviewState.model_validate_json(content)
```

해당 `InterviewState` JSON 경로에는 durable document `schema_version`이나
최상위 extra 거부 규칙이 없다. upstream checkpoint는
`CheckpointData`의 `hash` 필드로 무결성만 확인하며, 이것은 schema compatibility
version이 아니다. `persistence/migrations/runner.py`의 `_migrations` 테이블과
SQL 스크립트는 SQLite event store용이며 JSON 문서 계약을 마이그레이션하지
않는다.

따라서 이 결정은 upstream JSON state에 직접 대응물이 없는 의도적 divergence다.
upstream의 관찰은 “현재 JSON state에 version gate가 없다”는 사실의 근거로만
사용하며, 미래 스키마를 어떻게 변환할지는 upstream에서 추측하지 않는다.

## Decision

### 1. 다섯 최상위 durable model에 v1 계약을 둔다

각 모델에 다음을 추가한다.

```python
model_config = ConfigDict(frozen=True, extra="forbid")
schema_version: Literal[1] = 1
```

대상은 `BriefState`, `BlueprintState`, `ExecuteState`, `VerifyState`,
`MissionRecord`다. `schema_version`은 현재 지원하는 유일한 문서 버전이며,
`Literal[1]`이므로 `2`나 알 수 없는 값은 Pydantic validation error가 된다.

### 2. 버전 없는 기존 문서는 암묵적 v1로 읽는다

`schema_version`의 기본값은 기존 파일과의 호환을 위한 것이다. 필드가 없는
문서는 v1로 로드하고, 이후 `model_dump_json` 또는 repository save를 거치면
`schema_version: 1`을 포함해 기록한다. 기존 사용자 파일을 일괄 변환하거나
파일명을 바꾸지 않는다.

### 3. 미지 최상위 필드와 미지원 버전은 로드에서 중단한다

`extra="forbid"`는 다섯 저장 문서의 최상위 계약에 적용한다. 미지 최상위 필드나
지원하지 않는 `schema_version`은 repository에서 Pydantic `ValidationError`로
전파한다. 이 이슈에서는 자동 복구, 필드 삭제, 미래 버전 추측을 하지 않는다.

중첩 모델의 extra 정책을 일괄 변경하는 것은 이 결정의 범위가 아니다. 중첩
schema의 호환성 규칙은 해당 모델이 실제 durable contract로 확정될 때 별도
근거와 ADR로 결정한다.

### 4. 미래 버전은 새 ADR과 명시적 변환으로 도입한다

v2가 필요해지면 v1 문서를 v2 모델로 조용히 읽는 방식으로 확장하지 않는다.
지원 범위, 변환 가능성, 실패 시나리오, 저장 시점의 새 버전을 새 ADR과 회귀
테스트로 먼저 확정한다.

## Consequences

### Positive

- 알 수 없는 durable document를 정상 상태로 잘못 수용하지 않는다.
- 기존 versionless 문서는 깨뜨리지 않으면서 새 저장 문서의 형식이 드러난다.
- 다섯 repository load path가 같은 Pydantic 계약을 사용하므로 별도 parser drift가
  생기지 않는다.
- 향후 schema 변경 시 “현재 코드가 읽을 수 있는 문서”와 “읽어도 보존되지 않는
  문서”를 구분할 수 있다.

### Cost

- 새 필드나 버전을 저장 문서에 추가할 때 모델과 ADR·회귀 테스트를 함께 갱신해야
  한다.
- 운영 중인 파일에 미래 버전이나 오타가 있으면 load가 실패하며, 자동 fallback은
  제공하지 않는다.
- 최상위 검증만 이번 범위에 포함되어 중첩 문서의 compatibility 정책은 여전히
  별도 결정이 필요하다.

## Rejected alternatives

- **`extra="forbid"`만 적용**: 미지 필드의 손실은 막지만 문서가 어느 형식인지
  식별할 수 없어 의도적인 schema evolution 경계가 없다.
- **`schema_version`만 추가**: 미지 필드를 계속 무시하므로 오타와 미래 필드가
  round-trip에서 사라지는 문제가 남는다.
- **기존 파일을 즉시 일괄 마이그레이션**: 저장 파일을 모두 찾아 쓰는 운영 작업을
  요구하고, 현재 v1에 필요한 호환성보다 범위가 크다.
- **JSON에도 SQLite migration runner를 도입**: 아직 v2 변환 규칙이나 여러 단계의
  migration이 없으며, 저장 adapter의 검증 경계를 불필요하게 확장한다.
- **upstream처럼 versionless JSON을 유지**: 현재 issue가 입증한 조용한 데이터
  손실을 그대로 남긴다. upstream에 대응물이 없다는 사실은 이 위험을 수용해야
  한다는 근거가 아니다.

## Verification

- 다섯 durable model 각각에 `schema_version=1`이 기본값으로 들어간다.
- 다섯 repository load path가 versionless legacy JSON을 v1로 읽고, 저장 시
  version을 기록한다.
- 다섯 repository load path가 미지 최상위 필드와 `schema_version=99`를
  `ValidationError`로 거부한다.
- 기존 persistence·integration 전체 테스트와 `pytest`, `mypy`, `ruff`, format
  검증 게이트를 통과한다.
