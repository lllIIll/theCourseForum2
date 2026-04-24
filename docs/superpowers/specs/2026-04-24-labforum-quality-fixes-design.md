# LabForum Quality Fixes — Design Spec

**Branch:** `LabForum1`
**Date:** 2026-04-24
**Rubric target:** Exemplary (50/50) — well-structured, modular, readable, maintainable, clear naming, well-documented, easy to navigate.
**Author:** Luke + Claude Code, reviewed by OpenAI Codex (gpt-5.3-codex, high reasoning).

## Goal

Raise the `LabForum1` branch from "Proficient" to "Exemplary" quality before Jay reviews it. Five ordered commits, tests-first, CI-gated, each independently revertible.

## Current state (verified against the tree, not the earlier flawed audit)

- `tcf_website/models/` is already a package. `tcf_website/models/__init__.py` re-exports 25 classes from `tcf_website/models/models.py` (a single 2,224-line monolith). See `models/__init__.py:8-33`.
- Lab tests already exist:
  - `tcf_website/tests/test_lab_models.py` (171 LoC): covers Lab model, LabReview creation and vote/sort, LabVote unique constraint.
  - `tcf_website/tests/test_lab_views.py` (120 LoC): covers `/browse/?mode=labs` 200/contains-PI, plus `lab_detail` 200 and 404.
- Four classes with near-identical `upvote`/`downvote` methods:
  - `Review` at `models/models.py:1186`, methods at 1281 and 1307
  - `LabReview` at `models/models.py:1486`, methods at 1558 and 1565
  - `Question` at `models/models.py:1650`, methods at 1672 and 1698
  - `Answer` at `models/models.py:1749`, methods at 1771 and 1797
- Four corresponding vote tables: `Vote`, `LabVote`, `VoteQuestion`, `VoteAnswer`.
- `__init__.py` omits `VoteQuestion` and `VoteAnswer`. Pre-existing quirk; out of scope for this spec, noted in `doc/architecture.md`.
- `tcf_website/admin.py:8` uses `from .models import *`. Any symbol missing from `__init__.py` is effectively missing from admin.
- `AUTH_USER_MODEL = "tcf_website.User"` at `tcf_core/settings/base.py:139` is label-based, so moving `User` between files is safe as long as the class name is preserved.
- `apps.py` has no `ready()` override; no signal wiring to worry about.
- CI runs `coverage run manage.py test` and uploads a badge but enforces no coverage threshold (`.github/workflows/ci.yml:79`).

## What this spec is NOT

- Not a rewrite. Class names, field names, method signatures, and database schema stay identical.
- No new features. No UI changes. No migration-generating edits.
- Not a `legacy.py` consolidation. `tcf_website/legacy_models.py` stays where it is (moving it into the package risks confusing Django's migration diff).

## Commits (sequenced)

### Commit 1 — Expand lab test coverage

**Scope:** augment the existing `test_lab_models.py` and `test_lab_views.py`. No new `test_lab.py` file.

**Gaps to close (derived from `views/lab.py` and `models/models.py::LabReview`):**

In `test_lab_views.py`:
- `lab_detail` pagination: N+1 reviews, page 2 returns the overflow.
- `lab_detail` toxicity filter: `?toxicity=include` vs default, counts and visible reviews differ.
- `lab_detail` bar_width stats: posts with known rating distribution produce expected bar widths.
- `lab_detail` vote context for authenticated users: logged-in user's prior vote annotates the review.
- `lab_department` view at `views/lab.py:120`: returns 200, filters labs by `Department`, orders by `-is_recruiting` then `pi_name`, surfaces `review_count`/`avg_overall`/`avg_mentorship`/`avg_hours` annotations correctly. Breadcrumbs include school → department.

In `test_lab_models.py`:
- `LabReview` default field values (`hours_per_week`, `would_recommend`, `toxicity_rating`).
- `LabReview.__str__` format.
- Ordering stability on tie (same vote count, different `created_at`).

**Target size:** ~150-200 new LoC across the two files.

**Gate:** `python manage.py test tcf_website.tests.test_lab_models tcf_website.tests.test_lab_views` green; `pylint` clean on touched files.

### Commit 2 — Split `models/models.py` into domain submodules

**Structure after split:**
```
tcf_website/models/
├── __init__.py        (re-exports every public class; list grows but stays explicit)
├── course.py          Course, CourseGrade, CourseInstructorGrade, Discipline, Instructor,
│                      School, Section, SectionTime, Semester, Subdepartment, Department
├── review.py          Review, ReviewLLMSummary, Vote
├── lab.py             Lab, LabReview, LabVote
├── user.py            User
├── club.py            Club, ClubCategory
├── question.py        Question, Answer, VoteQuestion, VoteAnswer
└── schedule.py        Schedule, ScheduleBookmark, ScheduledCourse
```

**Rules:**
- Pure re-export from `__init__.py`. Every class currently in the re-export list stays in it. No call-site touches.
- All foreign keys use **string references** (`"Review"`, `"LabReview"`) rather than class imports. This avoids `ImportError` from circular module loading and `AppRegistryNotReady` from eager `apps.get_model()` calls at import time.
- No `apps.get_model()` at module top level. Any such usage stays inside method bodies.
- `legacy_models.py` stays outside the package. Not re-exported, not touched.

**Dependency move order** (ensures each intermediate state imports cleanly):
1. `user.py` (no deps)
2. `club.py` (depends on User)
3. `course.py` (School → Department → Subdepartment → Discipline → Instructor → Semester → Section → SectionTime → Course → CourseGrade → CourseInstructorGrade)
4. `schedule.py` (depends on course, user)
5. `review.py` (depends on course, user)
6. `lab.py` (depends on course, user; LabReview/LabVote)
7. `question.py` (depends on review via `Review` string reference)
8. Delete the now-empty original `models/models.py`.

Run `python manage.py test` and `python manage.py makemigrations --check` after **each** move. If either fails, abort the commit and investigate before continuing.

**Gate:** full test suite green; `makemigrations --check` reports no changes; `pylint tcf_website tcf_core` clean; `from tcf_website.models import *` still resolves every class the admin relies on.

**Rollback:** single-commit revert restores the monolith with zero call-site edits because nothing outside the package changed.

### Commit 3 — Extract `Votable` mixin across all 4 classes

**New file:** `tcf_website/models/mixins.py`

```
class Votable(models.Model):
    """Abstract base adding symmetric upvote/downvote/vote_count behavior.

    Subclasses must define `votes` as a reverse accessor to their vote table
    (Vote, LabVote, VoteQuestion, or VoteAnswer) and a class-level attribute
    `VOTE_MODEL` pointing to that vote model.
    """
    class Meta:
        abstract = True

    def upvote(self, user): ...
    def downvote(self, user): ...
    def vote_count(self): ...
```

**Scope: all four classes inherit Votable:**
- `Review` (with `VOTE_MODEL = Vote`)
- `LabReview` (with `VOTE_MODEL = LabVote`)
- `Question` (with `VOTE_MODEL = VoteQuestion`)
- `Answer` (with `VOTE_MODEL = VoteAnswer`)

Each class keeps its distinct vote table (different FKs, different `unique_together`). Only the method surface and signatures move to the mixin.

**Safety:**
- `mixins.py` imports nothing from other model submodules. Vote-model lookup happens via `self.VOTE_MODEL` or a string-reference pattern inside the method.
- Behavior parity preserved. No external API change. Existing upvote/downvote templates and JS keep working.

**Tests:** add `tcf_website/tests/test_votable_mixin.py`:
- Parity matrix: upvote/downvote/vote_count give identical results on Review, LabReview, Question, Answer for the same inputs.
- Idempotency: upvoting twice from the same user toggles/noop per current behavior (preserve what models.py did before).
- Existing test files (`test_review.py`, `test_lab_models.py`, `test_misc_models.py`) continue to pass unchanged.

**Gate:** full test suite green; `pylint` clean; `makemigrations --check` clean (mixin is abstract, no table change expected).

### Commit 4 — Scraper docstrings and follow-up docstring cleanup

**Targets (only the ones that are actually missing, per Codex verification):**
- `scripts/lab_scraper/` two-pass scraper entry points: top-level module docstring + function-level docstrings on the orchestrator and the diff-safety-gate functions.
- Any new helper introduced in commits 2-3 that lacks a docstring (likely the `Votable` mixin methods).

**Not re-done** because already documented:
- `views/lab.py::lab_detail` (`views/lab.py:15`)
- `views/lab.py::lab_department` (`views/lab.py:121`)
- `models.LabReview` class docstring (`models/models.py:1486` before split; `models/lab.py` after).

**Gate:** `pylint` clean; `pylint --disable=all --enable=missing-function-docstring,missing-module-docstring` clean on `scripts/lab_scraper/`.

### Commit 5 — CONTRIBUTING.md and doc/architecture.md

**`CONTRIBUTING.md`** (~100 LoC) at repo root:
- Pointer to `doc/dev.md` for setup.
- Branch conventions (feature branches off `dev`, no direct commits to `main`).
- Test-before-commit expectation: `python manage.py test` must pass before pushing.
- Linter commands: `pylint`, `black`, `isort`, `ESLint` with the exact flags CI uses.
- How to run the lab scraper safely (pointer to `scripts/lab_scraper/README.md`).
- PR expectations: description, test plan, screenshots if UI.

**`doc/architecture.md`** (~200 LoC) at `doc/architecture.md`:
- High-level map: `tcf_core` (settings, wsgi, urls) vs `tcf_website` (the app).
- Post-split `models/` package layout with one line per submodule describing contents.
- `views/` module boundaries (account, auth, catalog, courses, labs, review, schedule).
- Template and static asset conventions.
- LabForum dataflow: SEAS scraper → normalized JSON → Supabase staging → Django `load_labs` / `seed_lab_reviews` commands → `Lab` and `LabReview` models → `views/lab.py` → `templates/lab/`.
- "New code should import from the specific submodule" convention (the hybrid/C option from brainstorming).
- Known quirks worth calling out: `VoteQuestion`/`VoteAnswer` not re-exported through `__init__.py`; `admin.py` uses `from .models import *`; `AUTH_USER_MODEL` is label-based.

**Gate:** visual review; no markdownlint configured in repo, so no automated gate.

### Optional Commit 6 — CI coverage threshold gate

**Open question for user review.** If accepted:
- Edit `.github/workflows/ci.yml:79` block to run `coverage report --fail-under=75` after `coverage run`.
- Threshold 75% is conservative given current pre-existing coverage; raise later once baseline is established.
- If current baseline is below 75%, this commit cannot land as-is — first measure, then pick a threshold that fails forward-progress regressions without blocking current state.

**Decision:** flagged, not included by default. User to confirm before the plan execution step.

## Risk register

| Risk | Mitigation |
|---|---|
| Circular import between review.py and question.py (Answer references Review via Question which references Review) | String FK refs, no top-level class imports across submodules |
| `admin.py`'s wildcard import breaks on a missing name in `__init__.py` | Keep `__init__.py` re-export list as a superset of the pre-split public API; diff the list before and after |
| Pylint disables in the original monolith don't carry to submodules | Copy `# pylint: disable=...` directives to each submodule where the flagged pattern now lives |
| `makemigrations` sees a model-meta delta after split | Verify each submodule's class has the same `class Meta` (especially `db_table`, `app_label` if any). String FK refs prevent this automatically |
| Votable mixin changes vote idempotency subtly on one of the 4 classes | Behavior-parity tests per class compare before/after using the same fixtures |
| CI coverage gate blocks unrelated PRs | Pick threshold from measured baseline; flag as optional Commit 6 |

## Sequencing rationale (why this order, per Codex)

1. **Tests first** gives a safety net before any structural change. Existing lab tests are good but incomplete; filling the gaps now means Commits 2-3 can be verified by running the test suite.
2. **Split before mixin**. Pure structural reorganization is low-risk and behavior-preserving. Doing the Votable mixin first would mean editing the monolith, then re-editing the same methods when they move to their new home. Split once, refactor once.
3. **Docstrings after refactor**. Documenting the final shape of the code, not an intermediate one.
4. **Docs last**. `architecture.md` can only accurately describe the post-split layout.

## Open questions

1. **Coverage gate threshold** — accept Commit 6 with threshold 75%? Measure first and pick a threshold?
2. **VoteQuestion/VoteAnswer re-export** — include in `__init__.py` so admin can register them (scope expansion), or preserve the existing behavior (do nothing)?

Both default to "do the safe thing, document, move on" unless user overrides.

## Approval checkpoint

After user reviews this spec and confirms, hand off to `superpowers:writing-plans` to produce the step-by-step implementation plan.
