# LabForum Quality Polish — Part 2 (Deferred)

**Status:** Deferred. Not part of `LabForum1`.
**Branch this will land on:** TBD, separate feature branch off `dev` after `LabForum1` ships.
**Companion:** [2026-04-24-labforum-quality-fixes-design.md](./2026-04-24-labforum-quality-fixes-design.md) covers the organizational work that is shipping with `LabForum1`.

## Why deferred

`LabForum1` is a feature branch under review by Jay. Bundling code-quality refactors into it would bloat the PR and slow review. Part 1 ships the organizational win (models split + docs). This Part 2 captures the polish that pushes from "Proficient" toward "Exemplary" but isn't strictly organizational.

## Deferred items

### 1. Votable mixin across all 4 vote-bearing classes

Today four classes carry near-identical `upvote`/`downvote`/vote-count logic:
- `Review` (`models/review.py`, methods originally at `models/models.py:1281` and `:1307`)
- `LabReview` (`models/lab.py`, methods originally at `:1558` and `:1565`)
- `Question` (`models/question.py`, methods originally at `:1672` and `:1698`)
- `Answer` (`models/question.py`, methods originally at `:1771` and `:1797`)

**Plan:**
- New `tcf_website/models/mixins.py` with `class Votable(models.Model)` (abstract).
- Each subclass declares `VOTE_MODEL` (or equivalent class attribute pointing at its vote table: `Vote`, `LabVote`, `VoteQuestion`, `VoteAnswer`).
- Method bodies move to the mixin; subclasses inherit.
- Vote tables stay separate (different FKs, different `unique_together`).
- New `tests/test_votable_mixin.py` with parity tests across the four classes.

**Why deferred:** behavior refactor, not organization. Worth doing only if all 4 classes are unified — partial dedup is weak ROI.

### 2. Expand lab test coverage

Existing coverage in `tests/test_lab_models.py` and `tests/test_lab_views.py` is solid for the basics. Gaps to fill:

In `test_lab_views.py`:
- `lab_detail` pagination boundaries.
- `lab_detail` toxicity filter (`?toxicity=include`).
- `lab_detail` `bar_width` stats with known rating distributions.
- `lab_detail` vote-context annotations for authenticated users.
- `lab_department` view (currently uncovered): 200, filter-by-Department, `-is_recruiting`/`pi_name` ordering, breadcrumbs, annotation correctness.

In `test_lab_models.py`:
- `LabReview` default values for `hours_per_week`, `would_recommend`, `toxicity_rating`.
- `LabReview.__str__` format.
- Ordering stability on tied vote counts.

**Why deferred:** test discipline, not organization.

### 3. Scraper docstrings

`scripts/lab_scraper/` has a top-level README but the orchestrator and diff-safety-gate Python entry points lack module/function docstrings.

**Why deferred:** polish.

### 4. CI coverage threshold gate

`.github/workflows/ci.yml:79` runs `coverage report` but enforces no minimum. Add `coverage report --fail-under=<N>` after measuring the current baseline. Pick `N` to fail forward-progress regressions without blocking current state.

**Why deferred:** infra change with implications beyond the LabForum work.

### 5. Re-export `VoteQuestion` and `VoteAnswer`

`models/__init__.py` currently omits these two classes. `admin.py` uses `from .models import *`, so the admin can't register them. Either re-export them and add admin entries, or document the omission as intentional.

**Why deferred:** scope expansion outside organizational work.

## Sequencing if/when this lands

1. Create branch off `dev` after `LabForum1` is merged.
2. Items 1-5 in any order; each can be its own commit.
3. Item 4 (CI gate) should land last so the threshold reflects the post-polish baseline.

## Open questions

- **CI gate threshold:** measure baseline first, then pick. Likely 70-75% to start.
- **`VoteQuestion`/`VoteAnswer` re-export:** ship with admin entries, or just docs?
- **Votable scope:** any additional vote-bearing models added between now and then? Re-survey before extracting.
