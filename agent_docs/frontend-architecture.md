# theCourseForum Frontend Architecture

## Stack
- **Django 4.2.29** — server-side rendering with templates
- **Bootstrap 4.5.3** — CSS framework (CDN)
- **jQuery** — DOM manipulation (via Bootstrap)
- **Font Awesome** — icons (custom `icons.css`)
- **Google Fonts** — Lato, Open Sans
- **AWS Cognito** — authentication (OAuth 2.0)

## Template Hierarchy

```
base/index.html          ← HTML boilerplate, CDN links, GA/GTM
  └── base/base.html     ← sidebar + navbar + content wrapper
        ├── base/navbar.html    ← top nav: logo, search, account
        ├── base/sidebar.html   ← left rail: Browse, Review, Schedule, About, Sign In
        ├── base/messages.html  ← Django messages
        └── {% block content %} ← page-specific content
```

## Template Directories (72 files total)

| Directory | Templates | Purpose |
|-----------|-----------|---------|
| `base/` | 6 | Layout shell, navbar, sidebar, messages, bugform |
| `landing/` | 2 | Home page, dashboard |
| `browse/` | 2 | Browse page, school accordion component |
| `department/` | 2 | Department course listing, course card |
| `course/` | 2 | Course page, course+instructor detail |
| `instructor/` | 1 | Instructor profile page |
| `club/` | 3 | Club detail, category browse, mode toggle |
| `search/` | 2 | Search results, searchbar component |
| `reviews/` | 7 | Review form, review card, stats, modals |
| `schedule/` | 10 | Schedule builder, editor, modals |
| `qa/` | 3 | Q&A section, delete modals |
| `profile/` | 2 | User profile, delete modal |
| `about/` | 7 | About page, team, history, privacy, terms |
| `login/` | 1 | Login modal (Cognito) |
| `common/` | 9 | Toolbar, pagination, rating card, banners, ads |

## Static Files

### CSS (~24 files, ~2,600 lines)
Organized by feature: `base/`, `browse/`, `club/`, `course/`, `department/`, `instructor/`, `landing/`, `profile/`, `qa/`, `reviews/`, `schedule/`, `search/`, `common/`, `about/`, `icons/`, `login/`

### JS (~13 files, ~1,200 lines)
Key files:
- `search/filters.js` — advanced search with localStorage
- `reviews/review.js` — upvote/downvote AJAX
- `reviews/sort_reviews.js` — client-side review sorting
- `qa/qa.js` — Q&A interactions
- `schedule/parse_time.js` — schedule time parsing
- `common/recently_viewed.js` — localStorage recently viewed
- `club/mode_toggle.js` — courses/clubs toggle

## URL Structure (126 routes)

| Pattern | View | Page |
|---------|------|------|
| `/` | `index` | Landing page |
| `/browse/` | `browse` | Browse courses/clubs |
| `/department/<id>/` | `department` | Department course listing |
| `/course/<mnemonic>/<number>/` | `course_view` | Course detail |
| `/course/<course_id>/<instructor_id>/` | `course_instructor` | Instructor detail |
| `/instructor/<id>/` | `instructor_view` | Instructor profile |
| `/club-category/<slug>/` | `club_category` | Club category |
| `/search/` | `search` | Search results |
| `/reviews/new/` | `new_review` | Write review |
| `/reviews/` | `reviews` | My reviews |
| `/schedule/` | `view_schedules` | My schedules |
| `/profile/` | `profile` | User profile |
| `/about/` | `AboutView` | About page |
| `/login/` | `login` | Login (Cognito) |

## Navigation

### Sidebar (5 items)
1. Browse — `/browse/`
2. Review — `/reviews/new/`
3. Schedule — `/schedule/` (marked "New")
4. About — `/about/`
5. Sign In / Account — `/login/` or `/profile/`

### Top Navbar
- Left: tCF logo → `/`
- Center: search bar (courses/clubs toggle, filters dropdown)
- Right: history (recently viewed), account dropdown

## Design Tokens

| Token | Value | Usage |
|-------|-------|-------|
| Blue | `#4a6fa5` | School/instructor name blocks, card headers |
| Orange | `#d75626` | CTAs, active toggles, pills, accent borders |
| Page BG | `#f0f1f3` | Full page background |
| Card BG | `#fff` | Card backgrounds |
| Dark text | `#333` | Headings |
| Muted text | `#666` | Secondary text, breadcrumbs |
| Green | `#28a745` | Success badges ("No Application Required") |
| Font | Lato, Open Sans | Body text, headings |

## Key Patterns

- **Accordion:** Bootstrap collapse with blue card-header, chevron toggle, JS for expand/collapse
- **Breadcrumbs:** Gray card, `/` separator, last segment muted
- **Description cards:** White card, left orange border (4px), heading + body text
- **Stat columns:** Uppercase small labels (RATING, DIFFICULTY, etc.), em-dash for missing data
- **Mode toggle:** Sliding pill with orange indicator, `?mode=` query param
- **Pagination:** Django Paginator, rendered via `common/pagination.html`
- **AJAX voting:** POST to upvote/downvote endpoints, update DOM in place
- **Recently viewed:** localStorage, rendered in history modal
