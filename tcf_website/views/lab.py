"""Views for lab detail page and lab review voting."""

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse

from ..models import Department, Lab, LabReview


def lab_detail(request, slug):
    """Render the public lab profile page.

    Pulls the Lab by URL slug, aggregates the rating stats and the
    "would recommend" percentage, applies visibility filters to the
    review list (hidden, empty, toxic), annotates the review queryset
    with vote counts when the viewer is signed in, sorts/paginates,
    and hands the result to the template.
    """
    lab = get_object_or_404(Lab, slug=slug)

    # Average each rating dimension across all reviews of this lab.
    # avg_ratings() returns floats in [1, 5] or None if there are no
    # reviews; round so the template doesn't print 4.000000001.
    stats = lab.avg_ratings()
    stats = {k: round(v, 1) if v is not None else None for k, v in stats.items()}

    # Translate average ratings (1-5 scale) into pixel-percent widths
    # for the template's progress bars (0-100%). Multiplying by 20 maps
    # 5 -> 100, 1 -> 20. Missing values render as a zero-width bar.
    bar_widths = {}
    for key in ("mentorship", "lab_culture", "responsiveness", "independence", "entry_selectivity"):
        val = stats.get(key)
        bar_widths[key] = round(val * 20, 1) if val is not None else 0

    # "Would recommend" badge: percentage of reviewers who toggled
    # would_recommend=True. Computed in a single aggregate query so we
    # only hit the DB once instead of fetching every review row.
    recommend_data = lab.labreview_set.aggregate(
        total=Count("id"),
        recommend_count=Count("id", filter=Q(would_recommend=True)),
    )
    recommend_pct = None
    if recommend_data["total"] > 0:
        recommend_pct = round(
            100 * recommend_data["recommend_count"] / recommend_data["total"]
        )

    # Pull pagination + sort hints off the query string. Both have
    # safe defaults: page 1, no sort method (uses the model's default).
    page_number = request.GET.get("page", 1)
    method = request.GET.get("method", "")

    # Build the visible review list. Three filters are always applied:
    #   - hidden=False  (mod tools can soft-hide reviews)
    #   - text != ""    (skip empty-body reviews; they show up as blanks)
    # Toxicity filter only kicks in if the deployment defines a
    # TOXICITY_THRESHOLD; reviews scoring at-or-above the threshold
    # are excluded to keep abusive content off the public page.
    reviews = lab.labreview_set.filter(
        hidden=False,
    ).exclude(text="")

    if hasattr(settings, "TOXICITY_THRESHOLD"):
        reviews = reviews.filter(toxicity_rating__lt=settings.TOXICITY_THRESHOLD)

    # For signed-in viewers, annotate each review with two extra
    # numbers the template uses to render the vote widget:
    #   sum_votes  - net helpful score across everyone (upvotes - downvotes)
    #   user_vote  - this viewer's own current vote on the review (or 0)
    # Anonymous requests skip the annotation; the template degrades
    # gracefully and just hides the vote-state UI.
    if request.user.is_authenticated:
        reviews = reviews.annotate(
            sum_votes=Coalesce(Sum("labvote__value"), Value(0)),
            user_vote=Coalesce(
                Sum("labvote__value", filter=Q(labvote__user=request.user)),
                Value(0),
            ),
        )

    # Apply user-selected sort method, then chunk for pagination.
    reviews = LabReview.sort(reviews, method)
    paginated_reviews = LabReview.paginate(reviews, page_number)

    # Breadcrumbs follow the Labs > School > Department > PI hierarchy.
    # The school and department links route back to the labs browse so
    # users can hop around within the same school/department context.
    dept = lab.department
    breadcrumbs = [
        ("Labs", reverse("browse") + "?mode=labs", False),
        (dept.school.name, reverse("browse") + "?mode=labs", False),
        (dept.name, reverse("browse") + "?mode=labs", False),
        (lab.pi_name, None, True),
    ]

    # Lab.research_areas is a free-form comma-separated string from the
    # scraper. Split it into a clean list for the template tag chips.
    research_area_list = [
        a.strip() for a in lab.research_areas.split(",") if a.strip()
    ]

    return render(
        request,
        "site/lab/lab_detail.html",
        {
            "lab": lab,
            "stats": stats,
            "recommend_pct": recommend_pct,
            "review_count": recommend_data["total"],
            "paginated_reviews": paginated_reviews,
            "sort_method": method,
            "breadcrumbs": breadcrumbs,
            "research_areas": research_area_list,
            "bar_widths": bar_widths,
            "mode": "labs",
            "is_lab": True,
        },
    )


@login_required
def lab_upvote(request, review_id):
    """Toggle an upvote on a lab review for the signed-in user.

    Called via the lab review vote widget's POST endpoint. Idempotency
    (re-clicking upvote clears the vote) lives in LabReview.upvote(),
    inherited from the Votable mixin. Non-POST methods are rejected
    quietly so a casual GET to the URL doesn't mutate state.
    """
    if request.method == "POST":
        review = LabReview.objects.get(pk=review_id)
        review.upvote(request.user)
        return JsonResponse({"ok": True})
    return JsonResponse({"ok": False})


@login_required
def lab_downvote(request, review_id):
    """Toggle a downvote on a lab review for the signed-in user.

    Mirror of lab_upvote: same POST-only contract, same idempotent
    toggle semantics from the Votable mixin.
    """
    if request.method == "POST":
        review = LabReview.objects.get(pk=review_id)
        review.downvote(request.user)
        return JsonResponse({"ok": True})
    return JsonResponse({"ok": False})


def research_guide(request):
    """Render the static "how to find a lab" research guide page."""
    return render(request, "site/lab/research_guide.html", {"mode": "labs"})


def lab_department(request, dept_id):
    """List every lab in a department with aggregate review metrics.

    Mirrors the courses department page: same breadcrumb shape, same
    visual layout, same "recruiting first then alphabetic" ordering
    so labs and courses feel like one product. Counts and averages
    are computed in a single annotated query to keep page latency
    predictable as the dataset grows.
    """
    dept = get_object_or_404(Department, pk=dept_id)

    # Annotate each lab with review_count, avg_overall, avg_mentorship,
    # and avg_hours so the template can render the metric chips without
    # a second round-trip per row. distinct=True on review_count guards
    # against the row multiplication that joins normally produce.
    labs = (
        Lab.objects.filter(department=dept)
        .annotate(
            review_count=Count("labreview", distinct=True),
            avg_overall=Avg("labreview__overall"),
            avg_mentorship=Avg("labreview__mentorship"),
            avg_hours=Avg("labreview__hours_per_week"),
        )
        .order_by("-is_recruiting", "pi_name")
    )

    breadcrumbs = [
        (dept.school.name, reverse("browse") + "?mode=labs", False),
        (dept.name, None, True),
    ]

    return render(
        request,
        "site/catalog/lab_department.html",
        {
            "mode": "labs",
            "is_lab": True,
            "dept": dept,
            "labs": labs,
            "breadcrumbs": breadcrumbs,
        },
    )
