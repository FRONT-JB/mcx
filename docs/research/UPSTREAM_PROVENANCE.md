# Upstream provenance audit

> Checked: 2026-08-11
> Baseline: `Q00/ouroboros@9486c78575a0332e9b84d93ef5832985291d7943`
> (`v0.50.8`)
> Evidence level: **Verified — pinned source와 mcx source의 직접 대조**

## 1. 결론

기존의 “mcx는 observe-only라 upstream MIT 고지 조건이 발동하지 않았다”는 기록은
틀렸다. 설계 아이디어만 참고한 부분도 많지만, 일부 구현·정규식·prompt 계약은
upstream 표현을 그대로 옮기거나 구조적으로 포팅했다.

따라서 mcx의 FRONT-JB MIT 라이선스와 별도로 다음 upstream 고지를 배포물에
포함한다.

- Project: `Ouroboros` (`ouroboros-ai`)
- Source: `https://github.com/Q00/ouroboros`
- Version: `v0.50.8`
- Commit: `9486c78575a0332e9b84d93ef5832985291d7943`
- Copyright: `Copyright (c) 2025 Q00`
- License: MIT

## 2. 대조 방법과 한계

mcx와 pinned source의 `src/`·`skills/`·`tests/`에서 공백을 정규화해 장문 line,
연속 4-line block, Python string literal을 대조했다.

- 동일 장문 line 49개
- 동일 연속 4-line block 23개
- 동일한 40자 이상 Python string 11개

공통 import나 관용적 Python 구문도 섞이므로 숫자 전체를 복제량으로 해석하지
않는다. 다만 아래 high-signal 항목은 mcx 소스 주석도 “원문 그대로”, “정규식을
그대로”, “upstream 패턴 채택”이라고 명시하며 실제 pinned source와 일치한다.

## 3. 확인된 adapted surface

| mcx | pinned Ouroboros 대응물 | 확인 내용 |
|---|---|---|
| `domain/brief/requirement.py` | `core/requirement_candidate.py` | candidate enum 축과 promotion 판정 구조 |
| `domain/brief/derivation.py` | `bigbang/requirement_distillation.py` | 다국어 요구사항·constraint 정규식 |
| `domain/brief/closure.py` | `mcp/tools/subagent.py`, `agents/seed-closer.md` | closure lane prompt와 합성 계약 |
| `adapters/text/brief_backends.py` | `agents/socratic-interviewer.md` | interviewer 역할·질문 계약 문구 |
| `adapters/text/semantic_evaluator.py` | `evaluation/semantic.py` | semantic 판정 schema·지시 문구 |
| `domain/recover/packet.py` | `orchestrator/failure_taxonomy.py` | hard-precondition 정규식과 retry 분류 축 |
| `adapters/runtime/codex_execution_runtime.py` | `orchestrator/atomic_prompt_builder.py`, `resilience/recovery.py` | success/retry 계약 문구 |
| `adapters/workspace/checkpoint.py` | `auto/checkpoint_commits.py` | 제외 경로 정규식과 checkpoint 규칙 |
| `adapters/workspace/worktree.py` | `core/worktree.py` | cleanup 순회 일부와 worktree 정책 |
| `domain/blueprint/spec.py` | `core/seed.py`, `orchestrator/ac_execution_capsule.py` | verifiability field와 판정 일부 |

작은 공통 구문까지 파일별 저작권 고지 대상으로 단정하지 않는다. 위 표는 notice를
보존할 충분한 provenance가 확인된 범위를 기록한 것이며 법률 자문이 아니다.

## 4. 배포 계약

1. root `LICENSE`는 `Copyright (c) 2026 FRONT-JB`의 MIT로 유지한다.
2. root `THIRD_PARTY_NOTICES.md`에 위 식별 정보와 Q00의 MIT 전문을 보존한다.
3. Python `license-files`에 두 파일을 모두 등록해 wheel·sdist에 포함한다.
4. README에서 Ouroboros attribution과 notice를 연결한다.
5. 이후 upstream 표현을 새로 옮기면 이 inventory를 같은 변경에서 갱신한다.

## 5. 근거

- [pinned repository](https://github.com/Q00/ouroboros/tree/9486c78575a0332e9b84d93ef5832985291d7943)
- [pinned LICENSE](https://github.com/Q00/ouroboros/blob/9486c78575a0332e9b84d93ef5832985291d7943/LICENSE)
- [UPSTREAM_MAPPING §11](./UPSTREAM_MAPPING.md#11-license-note)
