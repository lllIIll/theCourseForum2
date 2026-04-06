---
title: "feat: Migrate Lab UI to New Site Design System"
type: feat
date: 2026-03-31
---

# Migrate Lab UI to New Site Design System

## Overview

The LabForum feature was built on the old Bootstrap 4 template stack (`base/base.html`). The rest of the site has since been migrated to a custom design system (`site/common/base.html`, CSS custom properties via `tokens.css`, BEM-style classes, inline SVGs). This plan ports all lab-facing pages into the new design system for visual consistency.

**Pages in scope:**
1. Lab detail page (`lab/lab_detail.html` → `site/lab/lab_detail.html`)
2. Lab review card partial (`lab/lab_review.html` → inline in detail or `site/lab/components/_lab_review_card.html`)
3. New lab review form (`reviews/new_lab_review.html` → `site/lab/lab_review_form.html`)
4. Browse catalog integration (update inline markup in `site/catalog/browse.html`)

**Not in scope:** Model or view logic changes. Views, URLs, vote endpoints are unchanged.

---

## Technical Approach

### Pattern to Follow

Every new-design detail page follows a two-section layout:

```
<div class="{entity}-header">
  <div class="{entity}-header__inner">   ← max-width: var(--size-max), responsive padding
    <nav class="breadcrumb">
    <div class="{entity}-header__title-row">
    <!-- subtitle / meta / actions row -->
  </div>
</div>
<div class="{entity}-content">           ← same max-width + padding
  <!-- cards, stats, reviews -->
</div>
```

Reference implementations:
- Club detail: `tcf_website/templates/site/clubs/club.html` + `css/site/pages/club.css`
- Course/Instructor: `tcf_website/templates/site/courses/course_instructor.html` + `css/site/pages/course_instructor.css`

Key conventions:
- No Bootstrap classes. All layout via CSS custom properties.
- Colors via `var(--accent)`, `var(--primary)`, `var(--fg-muted)`, etc. No hardcoded hex.
- Buttons: `.btn .btn--primary`, `.btn--accent`, `.btn--sm`, `.btn--md`
- Badges: `.badge .badge--success`, `.badge--default`, `.badge--warning`
- Inline SVG instead of FontAwesome `<i>` tags
- Sort: `<select class="select reviews-sort-select">`
- Pagination: `{% include "site/common/components/_pagination.html" %}`
- Vote buttons: `.vote-btn` with `.is-active` modifier (CSS-driven, no inline styles)
- Review cards: `<article class="review-card">` with `.review-card__header`, `__text`, `__category-grid`, `__footer`

---

## Implementation Phases

### Phase 1: CSS — `css/site/pages/lab.css`

**File:** `tcf_website/static/css/site/pages/lab.css` (new file)

Model after `club.css`. Sections needed:

```css
/* Lab Header */
.lab-header { ... }               /* padding, border-bottom, bg gradient */
.lab-header__inner { ... }        /* max-width: var(--size-max), responsive padding */
.lab-header__title-row { ... }    /* flex, align-items: baseline, gap */
.lab-header__title { ... }        /* font-display, text-5xl, font-normal */
.lab-header__department { ... }   /* text-lg, fg-muted */
.lab-header__meta { ... }         /* flex row, gap, mt-3 */

/* Lab Content */
.lab-content { ... }              /* max-width, responsive padding */

/* Info Card */
.lab-info-card { ... }            /* grid 1-col → 2-col at md, gap, padding, border-radius-2xl, bg-elevated, border */
.lab-info-card__main { ... }      /* research description + research area badges */
.lab-info-card__sidebar { ... }   /* contact links */
.lab-contact-link { ... }         /* flex, gap, items-center, fg-muted text */
.research-areas { ... }           /* flex wrap, gap-2 */

/* Stats Grid */
.lab-stats-grid { ... }           /* grid, 2-col → 4-col at md, gap-4, mb-8 */
.lab-stat-card { ... }            /* text-center, padding, border-radius-xl, bg-elevated, border */
.lab-stat-card__value { ... }     /* text-3xl, font-semibold, color: var(--accent) */
.lab-stat-card__label { ... }     /* text-xs, fg-muted, uppercase, letter-spacing */

/* Email Builder */
.lab-email-builder { ... }        /* collapsible card section */
.lab-email-builder__toggle { ... } /* btn--accent full-width toggle */

/* Reviews Section */
.lab-reviews { ... }              /* mt-8 */
.lab-reviews__header { ... }      /* flex justify-between align-center mb-6 */
.lab-reviews__title { ... }       /* text-2xl, font-semibold */
.lab-reviews__actions { ... }     /* flex gap-3 */

/* Review card lab-specific categories */
/* (reuse .review-card from course_instructor.css — no duplication) */
```

**Also:** Add `lab.css` to `main.css` is NOT needed — page-specific CSS is loaded per-page via `{% block styles %}`.

---

### Phase 2: Lab Detail Template

**File:** `tcf_website/templates/site/lab/lab_detail.html` (new file)

**Extends:** `site/common/base.html`

**Structure:**

```html
{% extends "site/common/base.html" %}
{% load static %}{% load custom_tags %}

{% block styles %}
<link rel="stylesheet" href="{% static 'css/site/pages/course_instructor.css' %}">
<link rel="stylesheet" href="{% static 'css/site/pages/lab.css' %}">
{% endblock %}

{% block content %}

<!-- Header -->
<div class="lab-header">
  <div class="lab-header__inner">
    <nav class="breadcrumb" aria-label="Breadcrumb">
      {% for crumb in breadcrumbs %}...{% endfor %}
    </nav>

    <div class="lab-header__title-row">
      <h1 class="lab-header__title">{{ lab.pi_name }}</h1>
      <span class="lab-header__department">{{ lab.department.name }}{% if lab.title %} · {{ lab.title }}{% endif %}</span>
    </div>

    <div class="lab-header__meta">
      {% if lab.is_recruiting %}
      <span class="badge badge--success">Actively Recruiting</span>
      {% endif %}
      <span class="badge badge--default">{{ review_count }} Review{{ review_count|pluralize }}</span>
    </div>
  </div>
</div>

<!-- Content -->
<div class="lab-content">

  <!-- Stats Grid (only if reviews exist) -->
  {% if stats.overall %}
  <div class="lab-stats-grid">
    <!-- 8 stat cards: overall, mentorship, culture, work_life, inclusivity, responsiveness, hours_per_week, recommend_pct -->
  </div>
  {% endif %}

  <!-- Info Card -->
  <div class="lab-info-card">
    <div class="lab-info-card__main">
      {% if lab.description %}<p>{{ lab.description }}</p>{% endif %}
      {% if research_areas %}
      <div class="research-areas">
        {% for area in research_areas %}<span class="badge badge--default">{{ area }}</span>{% endfor %}
      </div>
      {% endif %}
    </div>
    <div class="lab-info-card__sidebar">
      <!-- Contact links: email, office, phone, profile_url, website, google_scholar, github_url -->
      <!-- Each as .lab-contact-link with inline SVG icon -->
    </div>
  </div>

  <!-- Email Builder (collapsible, only if lab.email) -->
  {% if lab.email %}
  {% include "lab/email_builder.html" %}   {# keep existing email builder logic unchanged #}
  {% endif %}

  <!-- Reviews -->
  <section class="lab-reviews" id="reviews">
    <div class="lab-reviews__header">
      <h2 class="lab-reviews__title">{{ review_count }} Review{{ review_count|pluralize }}</h2>
      <div class="lab-reviews__actions">
        {% if user.is_authenticated %}
        <a href="{% url 'new_review' %}?mode=labs&lab={{ lab.id }}" class="btn btn--accent btn--md">
          <!-- plus SVG --> Add Review
        </a>
        {% else %}
        <a href="#" class="btn btn--accent btn--md" data-action="login">
          <!-- plus SVG --> Add Review
        </a>
        {% endif %}
        {% if review_count > 0 %}
        <select class="select reviews-sort-select" id="review-sort" aria-label="Sort reviews">
          <option value="">Sort by...</option>
          <option value="Most Helpful" ...>Most Helpful</option>
          <option value="Most Recent" ...>Most Recent</option>
          <option value="Highest Rating" ...>Highest Rating</option>
          <option value="Lowest Rating" ...>Lowest Rating</option>
        </select>
        {% endif %}
      </div>
    </div>

    {% for review in paginated_reviews %}
    {% include "site/lab/components/_lab_review_card.html" with review=review %}
    {% empty %}
    <!-- empty state -->
    {% endfor %}

    {% include "site/common/components/_pagination.html" with paginated_items=paginated_reviews anchor="reviews" %}
  </section>

</div>
{% endblock %}

{% block scripts %}
<script src="{% static 'lab/lab_review.js' %}"></script>  {# vote JS — unchanged #}
{% endblock %}
```

**Update `views/lab.py`:** Change `render(request, "lab/lab_detail.html", ...)` to `"site/lab/lab_detail.html"`.

---

### Phase 3: Lab Review Card Partial

**File:** `tcf_website/templates/site/lab/components/_lab_review_card.html` (new file)

Uses the `.review-card` BEM structure from `course_instructor.css` (already loaded via Phase 2). Lab-specific category labels differ from course reviews:

```html
<article class="review-card">
  <div class="review-card__header">
    <div class="review-card__context">
      <span class="review-card__semester">{{ review.get_role_display }}</span>
      <div class="review-card__meta">
        <span>{{ review.period }}</span>
        <span>{{ review.hours_per_week }} hrs/wk</span>
      </div>
    </div>
    <div class="review-card__ratings">
      <div class="review-rating">
        <div class="review-rating__value">{{ review.overall }}</div>
        <div class="review-rating__label">Overall</div>
      </div>
      {% if review.would_recommend %}
      <span class="badge badge--success">Would Recommend</span>
      {% else %}
      <span class="badge badge--default">Would Not Recommend</span>
      {% endif %}
    </div>
  </div>

  {% if review.text %}
  <p class="review-card__text">{{ review.text|linebreaksbr }}</p>
  {% endif %}

  <!-- 6-category grid: mentorship, work_life, friendliness, inclusivity, responsiveness -->
  <div class="review-card__category-grid">
    <div class="review-category"><span class="review-category__label">Mentorship</span><span class="review-category__value">{{ review.mentorship }}</span></div>
    <div class="review-category"><span class="review-category__label">Work-Life</span><span class="review-category__value">{{ review.work_life }}</span></div>
    <div class="review-category"><span class="review-category__label">Culture</span><span class="review-category__value">{{ review.friendliness }}</span></div>
    <div class="review-category"><span class="review-category__label">Inclusivity</span><span class="review-category__value">{{ review.inclusivity }}</span></div>
    <div class="review-category"><span class="review-category__label">Responsiveness</span><span class="review-category__value">{{ review.responsiveness }}</span></div>
  </div>

  {% if review.advice %}
  <details class="review-card__details">
    <summary>Advice for future students</summary>
    <p>{{ review.advice }}</p>
  </details>
  {% endif %}

  <div class="review-card__footer">
    <div class="review-card__votes">
      <button class="vote-btn {% if review.user_vote > 0 %}is-active{% endif %}"
              type="button" data-action="upvote" data-review="{{ review.id }}">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="m5 15 7-7 7 7"/></svg>
        <span>{{ review.sum_votes|default:0 }}</span>
      </button>
      <button class="vote-btn {% if review.user_vote < 0 %}is-active{% endif %}"
              type="button" data-action="downvote" data-review="{{ review.id }}">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="m19 9-7 7-7-7"/></svg>
      </button>
    </div>
    <span class="review-card__date">{{ review.created|date:"M j, Y" }}</span>
  </div>
</article>
```

---

### Phase 4: New Lab Review Form

**File:** `tcf_website/templates/site/lab/lab_review_form.html` (new file — replaces `reviews/new_lab_review.html`)

**Extends:** `site/common/base.html`
**CSS:** `{% static 'css/site/pages/review.css' %}` (reuse existing review form styles)

Structure mirrors the new course/club review form (`site/review/review.html`) but with lab-specific fields:

- **Header:** "Review [PI Name]'s Lab" with breadcrumb
- **Rating inputs:** Use the segmented rating pattern from `review.css` (if it exists) or `<select class="select">` dropdowns for each rating dimension (overall, mentorship, work_life, friendliness, inclusivity, responsiveness)
- **Role select:** `<select class="select">` for role choices
- **Text fields:** `<textarea class="textarea">` for text, how_joined, advice
- **Hours input:** `<input class="input" type="number">`
- **Would-recommend:** Toggle buttons with `.btn` classes (no Bootstrap `btn-group-toggle`)
- **Submit:** `.btn .btn--accent .btn--lg`

**Update `views/review/new_review.py`:** Change `"reviews/new_lab_review.html"` render path to `"site/lab/lab_review_form.html"`.

---

### Phase 5: Browse Catalog Integration

**File:** `tcf_website/templates/site/catalog/browse.html` (update existing)

The current lab browse section uses raw Bootstrap-style classes. Replace the `{% elif is_lab %}` block to use a proper component:

**New file:** `tcf_website/templates/site/catalog/components/_lab_school_section.html`

Model after `tcf_website/templates/site/catalog/components/_school_section.html`. Each school expands to show departments, each department shows a list of labs with recruiting badge.

Update `site/catalog/browse.html`:
```django
{% elif is_lab %}
<div id="browse-default-catalog">
  {% for school in lab_schools %}
  {% include "site/catalog/components/_lab_school_section.html" with school=school %}
  {% empty %}
  <p class="text-muted">No labs found.</p>
  {% endfor %}
</div>
```

---

## Acceptance Criteria

### Functional
- [ ] `/lab/<slug>/` renders via `site/common/base.html` (header/footer present, dark mode toggle works)
- [ ] Breadcrumb shows: Labs → [School] → [Department] → [PI Name]
- [ ] Stats grid visible only when `stats.overall` is truthy
- [ ] "Actively Recruiting" badge shows correctly
- [ ] Research areas display as badges
- [ ] Contact links render with SVG icons (email, office, website, google scholar, github)
- [ ] Email builder section present if `lab.email` exists
- [ ] Review sort select works (page reloads with `?method=` param)
- [ ] Vote buttons work (up/down, `.is-active` reflects current user vote)
- [ ] Pagination renders correctly
- [ ] "Add Review" → logged-out users see login prompt
- [ ] New lab review form extends new site base, submits correctly, validation errors shown
- [ ] Browse labs page (`/browse?mode=labs`) uses `_lab_school_section.html` component

### Visual
- [ ] No Bootstrap 4 classes in any rendered HTML for lab pages
- [ ] No hardcoded hex colors (no `#d75626`, `#4a6fa5` inline)
- [ ] Page matches the visual feel of club detail page
- [ ] Dark mode renders correctly on all lab pages

### Non-Functional
- [ ] Old template paths (`lab/lab_detail.html`, `reviews/new_lab_review.html`) can be deleted after views are updated
- [ ] Vote JS (`lab/lab_review.js`) unchanged — only update `data-action` attributes to match expected values

---

## File Checklist

### New files to create
- `tcf_website/static/css/site/pages/lab.css`
- `tcf_website/templates/site/lab/lab_detail.html`
- `tcf_website/templates/site/lab/components/_lab_review_card.html`
- `tcf_website/templates/site/lab/lab_review_form.html`
- `tcf_website/templates/site/catalog/components/_lab_school_section.html`

### Files to update
- `tcf_website/views/lab.py` — update template paths (lines ~30, ~80)
- `tcf_website/views/review/new_review.py` — update lab review form path
- `tcf_website/templates/site/catalog/browse.html` — replace `{% elif is_lab %}` block

### Files to delete (after views updated)
- `tcf_website/templates/lab/lab_detail.html`
- `tcf_website/templates/lab/lab_review.html`
- `tcf_website/templates/reviews/new_lab_review.html`
- `tcf_website/static/lab/lab_detail.css` (replaced by `css/site/pages/lab.css`)

### Files to keep unchanged
- `tcf_website/templates/lab/email_builder.html` — included as-is, no base template
- `tcf_website/templates/lab/browse_school.html` — superseded by new component but keep until browse is verified
- `tcf_website/static/lab/lab_review.js` — vote JS still works
- `tcf_website/static/lab/email_builder.js` / `email_builder.css` — keep until email builder is restyled (separate task)

---

## Key References

- Club detail template (closest analog): `tcf_website/templates/site/clubs/club.html`
- Club CSS (structure to copy): `tcf_website/static/css/site/pages/club.css`
- Review card CSS (reuse directly): `tcf_website/static/css/site/pages/course_instructor.css:631–796`
- Design tokens: `tcf_website/static/css/site/tokens.css`
- Vote JS pattern: `tcf_website/static/js/site/review/review_votes.js`
- Lab view context vars: `tcf_website/views/lab.py:1–106`
- Pagination component: `tcf_website/templates/site/common/components/_pagination.html`
