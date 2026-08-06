# ADR 0006 — Dual terminology with stable mapping

- Status: Accepted
- Date: 2026-08-07
- Constitutional basis: Canonical Terminology

## Context

Mission Control은 고유한 제품 경험이 필요하지만, 이 프로젝트의 v1 목표는
Ouroboros의 설계를 재구성하고 직접 비교하는 것이다. 내부 용어까지 모두 바꾸면
원본 코드와 문서를 읽을 때 불필요한 번역 비용이 생긴다.

## Decision

사용자-facing 용어와 내부/upstream 용어를 1:1로 유지한다.

| 사용자 용어 | 내부 용어 |
|---|---|
| Brief | Interview |
| Blueprint | Seed |
| Execute | Run |
| Verify | Evaluate |
| Recover | Repair |

CLI는 `mcx brief`, `mcx blueprint`, `mcx execute`, `mcx verify`, `mcx recover`를
사용한다. 구현 문서와 upstream mapping은 내부 용어를 함께 표시한다.

Gate 결과는 `CLEAR`, `HOLD`, 최종 성공은 `MISSION COMPLETE`다.

## Consequences

### Positive

- 제품 정체성과 원본 추적성을 동시에 유지한다.
- 새 세션이 CLI와 코드 용어를 빠르게 연결할 수 있다.
- 원본 diff와 학습 문서를 직관적으로 작성할 수 있다.

### Cost

- 문서에서 최초 등장 시 두 이름을 병기해야 한다.
- 저장 enum이 어느 언어를 사용할지는 별도 결정이 필요하다.
- 용어 매핑이 drift하지 않도록 테스트와 문서 검사가 필요하다.

## Rejected alternatives

- CLI와 코드 모두 Ouroboros 용어를 사용한다.
- 내부 클래스와 개념까지 Mission Control 세계관으로 전부 바꾼다.
- 단계마다 임의의 동의어를 허용한다.

## Verification

- CLI help와 Stage docs가 같은 mapping을 사용한다.
- 이전 후보 프로젝트명이나 `NO-GO`가 current API에 노출되지 않는다.
- upstream mapping table이 모든 Stage를 1:1로 연결한다.

