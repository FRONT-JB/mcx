# upstream checkpoint 커밋 조사 — `auto/checkpoint_commits.py`

- 조사일: 2026-08-09
- Baseline: `~/.claude/plugins/marketplaces/ouroboros` @ `9486c78` (v0.50.8)
- Evidence level: **source-read**
- 소비처: [ADR-0046](../adr/0046-verified-checkpoint-commits.md)

파일: `src/ouroboros/auto/checkpoint_commits.py` (185줄).
docstring: *"Git checkpoint commits for verified auto acceptance criteria."*

---

## 1. 커밋 시점은 **실행 뒤가 아니라 검증 뒤**다

호출 지점은 하나뿐이다 — `mcp/tools/evolution_handlers.py:1162`, 즉
`evolve_step`(한 세대의 **평가가 끝난 뒤**)이다. Execute 경로에는 없다.

```python
for ac in evaluation_summary.ac_results:
    if not bool(getattr(ac, "authoritative_pass", False)):
        continue
    checkpoint_passed_ac(state, repo_cwd=repo_cwd, ac_id=ac_id, ac_text=ac_text)
```

`authoritative_pass`는 `core/lineage.py:100`에서 정의된다:

```python
return self.passed and self.verdict_is_authoritative
```

`verdict_is_authoritative`는 *"완료된 evaluator/verifier 판정을 기록하고 있는가"*
이며, override된 판정은 **검증 방법과 증거가 둘 다 있어야** 권위를 얻는다.

즉 커밋 조건은 *"실행됐다"* 가 아니라 **"증거로 통과가 입증됐다"** 이다.
검증되지 않은 변경은 커밋하지 않으므로, 남은 커밋은 전부 되돌릴 수 있는
기준점이 된다.

## 2. "AC별"은 라벨이지 분할이 아니다

`checkpoint_passed_ac`는 호출 시점의 **작업 트리 전체 변경**을 스테이징한다
(`git status --porcelain=v1 -z --untracked-files=all`). AC의 파일 목록을 따로
계산하지 않는다.

따라서 한 평가 라운드에서 AC 세 개가 통과하면 **첫 AC가 그 라운드의 변경을
전부 가져가고**, 나머지 둘은 `no_staged_changes`로 건너뛴다. AC 단위 분할이
아니라 **라운드 단위 커밋에 AC 이름을 붙이는 것**이다.

세대를 거듭하면 각 세대가 자기 delta를 커밋하므로 결과적으로 증분이 쌓인다.

## 3. 비밀 경로는 스테이징에서 뺀다

```python
_SECRET_PATH_RE = re.compile(r"(^|/)(\.env(?:\.|$)|.*secret.*|.*credential.*)", re.IGNORECASE)
```

걸러낸 뒤 남은 경로가 없으면 `no_safe_changes`로 건너뛴다. 그리고 커밋은
`git commit -m ... -- <safe_paths>`로 **경로를 명시**한다 — `git commit -a`가
아니다. 즉 걸러낸 파일이 우연히 실려 가지 않는다.

## 4. 멱등성은 상태에 기록한다 — 실패한 시도까지

```python
if any(entry.get("ac_id") == ac_id for entry in state.checkpoint_commits):
    return ... reason="already_committed"
if ac_id in state.checkpoint_attempted_ac_ids:
    return ... reason="already_attempted"
state.checkpoint_attempted_ac_ids.append(ac_id)
```

**시도 기록이 커밋 기록보다 먼저 남는다.** 커밋에 실패한 AC를 다음 라운드에서
다시 시도하지 않는다는 뜻이다.

## 5. 실패는 미션을 죽이지 않는다

```python
except RuntimeError as exc:
    log.warning("mcp.tool.evolve_step.checkpoint_commit_failed", error=str(exc))
```

건너뛰는 사유는 결과 객체에 남는다: `commit_policy`, `already_committed`,
`already_attempted`, `not_git_repo`, `no_safe_changes`, `no_staged_changes`.

## 6. 커밋 메시지 형태

```
ooo: satisfy AC-1 <AC 텍스트 48자 요약>       ← 72자로 자름

Auto-Session: <auto_session_id>
Execution-Id: <execution_id 또는 none>
Acceptance-Criterion: <ac_id>
```

`final_only` 정책일 때는 `ooo: complete auto session ...` + `Commit-Policy: final_only`.

## 7. 정책 셋과 기본값

`AutoCommitPolicy`: `ac_checkpoint` · `final_only` · `none`.

| 프로파일 | 기본 |
|---|---|
| coding | `ac_checkpoint` (`auto/profiles/coding.py:20`) |
| 그 외 / 미상 | `none` (`auto/policies.py:30`) |

`policies.py`의 주석이 이유를 적는다:

> *"Non-coding / unknown domains never auto-commit or relocate the caller's
> checkout by default. Final-only commits on the current checkout are an
> explicit operator opt-in rather than a silent side effect."*

→ **사용자의 checkout에 조용히 커밋하지 않는다**가 기본값 설계의 근거다.
`AutoPipelineState`의 클래스 기본값도 `NONE`이다.

## 8. worktree 정책과 짝을 이룬다

같은 자리에서 `DEFAULT_WORKTREE_POLICY = AUTO`가 함께 설정된다
(`profiles/coding.py:21`). 즉 upstream에서 **자동 커밋과 격리는 같은 프로파일
결정으로 함께 켜진다** — 격리 없이 자동 커밋만 켜지는 조합을 기본값으로 두지
않는다.

---

## 우리 쪽 대응 지점 (조사 시점의 사실)

- Verify는 **일괄**이다 — `verify mechanical`이 전체 AC의 명령을 돌리고
  `verify semantic`이 전체를 판정한다. upstream의 세대 루프에 해당하는 것은
  **한 번의 검증 라운드**다.
- AC 하나의 통과 판정은 `evaluate_verify_gate`가 AC마다 blocker를 붙이는
  형태로 이미 존재한다 (`domain/verify/gate.py`). blocker가 없는 AC가 통과다.
- 커밋할 자리는 `attempts[-1].envelope.workspace`이며, ADR-0045로 그것은 미션
  전용 worktree다 — 사용자 checkout에 커밋하는 경로가 구조적으로 없다.
- 비밀 경로 규칙은 [ADR-0040](../adr/0040-secret-redaction-boundaries.md)이
  이미 자격증명 경계를 정해 두었다. 파일 경로 필터는 그 ADR에 없는 축이다.
