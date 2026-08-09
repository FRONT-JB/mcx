# upstream 되돌리기 조사 — rollback · rewind · 세대 태그

- 조사일: 2026-08-09
- Baseline: `~/.claude/plugins/marketplaces/ouroboros` @ `9486c78` (v0.50.8)
- Evidence level: **source-read**
- 소비처: [ADR-0032](../adr/0032-recover-deliberate-divergences.md) rollback 보류 해제

## 0. ADR-0032의 근거 포인터가 틀렸다

[ADR-0032](../adr/0032-recover-deliberate-divergences.md)는 *"rollback / worktree
복구"* 의 upstream 근거를 `core/worktree.py`로 적어 두었다. **그 파일에는
되돌리기가 없다** — 2026-08-09 전수 확인. `core/worktree.py`가 하는 일은 격리와
lock과 정리뿐이며, 정리조차 dirty checkout을 **거부**한다
([WORKTREE findings](./WORKTREE_UPSTREAM_FINDINGS.md) §5).

되돌리기는 다른 두 곳에 있고 **성격이 서로 다르다.**

## 1. 되돌리기는 두 층이며, 권위는 이벤트 쪽이다

| 층 | 무엇을 되돌리나 | 어디 |
|---|---|---|
| **lineage rewind** | 세대 이력(스펙 계보) | `core/lineage.py`, `evolution/loop.py` (Python Core) |
| **git rollback** | 작업 트리 파일 | `scripts/ralph.sh` (**셸 스크립트**) |

`OntologyLineage.rewind_to`는 **파일을 건드리지 않는다** — 세대 튜플을 잘라내고
상태를 `ACTIVE`로 되돌린 새 객체를 반환하는 순수 함수다.

```python
truncated = tuple(g for g in self.generations if g.generation_number <= generation_number)
return self.model_copy(update={"generations": truncated, "status": LineageStatus.ACTIVE})
```

docstring: *"This enables snapshot/rewind: rewind to Oₙ and branch from there."*
즉 **되감기의 1차 의미는 "스펙 계보를 어디서 다시 갈라지게 할 것인가"** 이고,
파일 복구는 그것을 따라가는 부수 작업이다.

## 2. 파일 되돌리기는 Core가 아니라 **셸 스크립트**에 있다

`scripts/ralph.sh`에 두 함수가 있다.

**`tag_generation`** — 세대가 성공하면 커밋하고 태그를 붙인다.

```sh
git add -A
git commit -m "ooo: gen ${gen} [${LINEAGE_ID}]"
git tag -f "ooo/${LINEAGE_ID}/gen_${gen}"
```

- **실패한 세대에는 태그를 붙이지 않는다** (`action != failed`일 때만 호출).
- `--no-execute`면 건너뛴다 — 코드 변경이 없는 세대는 스냅샷 대상이 아니다.
- git 저장소가 아니면 조용히 통과한다.
- 태그는 `-f`로 덮어쓴다 (재실행 대비).

**`rollback_to_previous`** — 세대가 **실패했을 때만** 부른다 (`action = failed`).

```sh
git checkout "ooo/${LINEAGE_ID}/gen_$((gen-1))" -- .
git reset HEAD
git clean -fd
```

**되돌리기 범위는 "직전 성공 세대"** 이며 임의 지점이 아니다. 이전 태그가 없으면
건너뛴다. checkout이 실패해도 경고만 남기고 진행한다(`|| { log WARNING; return 0; }`).

> `git checkout <tag> -- .`는 **HEAD를 옮기지 않는다.** 작업 트리와 인덱스만
> 그 시점으로 되돌리고, 뒤이은 `reset HEAD`가 인덱스를 풀며 `clean -fd`가
> 추적되지 않은 파일을 지운다. 즉 **커밋 이력은 남고 트리만 되감긴다.**

## 3. `git reset --hard`는 되돌리기에 쓰이지 않는다

전 소스에서 `reset --hard`는 **한 군데뿐**이며, PM brownfield 스냅샷 worktree를
원격 기본 브랜치로 갱신하는 자리다 (`core/pm_snapshot.py:154`). 미션 작업을
되돌리는 경로가 아니다.

## 4. rewind의 git 부분은 **best-effort**이고, dirty면 하지 않는다

TUI(`tui/screens/lineage_detail.py:525-605`)의 순서가 계약을 드러낸다.

1. lineage rewind를 **먼저 커밋**한다 (이벤트가 권위).
2. `git status --porcelain`을 본다. **dirty면 checkout을 건너뛰고**
   *"Rewind (partial) — Git checkout skipped, working tree is dirty"* 로 알린다.
3. 태그가 없으면 역시 건너뛰고 *"Rewind (partial)"*.
4. 그제서야 `git checkout <tag>` (여기서는 `-- .`가 아니라 **detached HEAD**).

**세 지점 모두 사용자의 변경을 덮지 않는다.** 되돌리기가 부분적으로만 일어난
것을 숨기지 않고 partial로 알린다.

같은 흐름이 `scripts/ralph-rewind.py`에도 있고, 그쪽은 git checkout이
**옵트인**이다 (`--checkout` 플래그, 기본은 안 함).

## 5. 되돌리기 뒤 무엇이 살아남는가 — `frozen_ac_indices`

세대는 `frozen_ac_indices`를 들고 있다 (`core/lineage.py:397`). 이미
`authoritative_pass`인 AC는 다음 세대의 작업 집합에서 **얼린다**
(`evolution_handlers.py:946-954`). 즉 되돌린 뒤에도 *"입증된 AC는 다시 하지
않는다"* 가 유지된다.

이것이 [checkpoint](./CHECKPOINT_UPSTREAM_FINDINGS.md)와 같은 축이다 —
입증(`authoritative_pass`)이 커밋 단위이자 재작업 제외 단위다.

## 6. 요약: upstream의 되돌리기 계약

- **되돌릴 지점은 성공한 세대의 태그다.** 실패한 세대는 지점을 만들지 않는다.
- **범위는 직전 성공 세대**이며, 임의 커밋으로 가는 자동 경로는 없다(사용자가
  rewind에서 세대를 고를 때만 지점이 정해진다).
- **파괴적 연산을 쓰지 않는다** — `reset --hard`가 아니라 트리 복원 +
  `clean -fd`. 커밋 이력은 남는다.
- **dirty면 하지 않는다.** 사용자의 미커밋 변경을 덮는 경로가 없다.
- **실패해도 미션을 죽이지 않는다.** 경고와 partial 표시로 끝난다.
- **자동 rollback은 세대 실패 한 경우뿐이다.** 그 외에는 사용자가 rewind로
  지점을 고른다.
- **위치가 Core가 아니다** — 파일 되돌리기는 셸 스크립트, Core는 계보만 다룬다.

---

## 우리 쪽 대응 지점 (조사 시점의 사실)

- 되돌릴 지점이 [ADR-0046](../adr/0046-verified-checkpoint-commits.md)으로
  생겼다 — **입증된 것만 커밋**하므로 upstream의 *"성공한 세대에만 태그"* 와 같은
  성질을 이미 갖는다. 태그는 없고 커밋이 그 자리다.
- 실행이 도는 곳은 미션 전용 worktree이며 브랜치는 `mcx/<mission_id>`다
  (ADR-0045). 사용자의 checkout을 되돌릴 경로가 구조적으로 없다.
- 우리에겐 셸 스크립트 계층이 없다 — upstream이 `ralph.sh`에 둔 것을 어디에 둘지가
  결정 사항이다.
- `frozen_ac_indices`의 대응물은 없다. 우리 Recover는 실패한 AC를 재투입하지만
  *"입증된 AC를 다시 하지 않는다"* 를 명시적으로 표현하는 필드가 없다.
