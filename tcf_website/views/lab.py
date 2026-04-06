"""Views for lab detail page and lab review voting."""

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse

from ..models import Lab, LabReview


def lab_detail(request, slug):
    """Lab detail page."""
    lab = get_object_or_404(Lab, slug=slug)

    # Aggregate ratings
    stats = lab.avg_ratings()
    stats = {k: round(v, 1) if v is not None else None for k, v in stats.items()}

    # Would recommend percentage
    recommend_data = lab.labreview_set.aggregate(
        total=Count("id"),
        recommend_count=Count("id", filter=Q(would_recommend=True)),
    )
    recommend_pct = None
    if recommend_data["total"] > 0:
        recommend_pct = round(
            100 * recommend_data["recommend_count"] / recommend_data["total"]
        )

    # Reviews
    page_number = request.GET.get("page", 1)
    method = request.GET.get("method", "")

    reviews = lab.labreview_set.filter(
        hidden=False,
    ).exclude(text="")

    if hasattr(settings, "TOXICITY_THRESHOLD"):
        reviews = reviews.filter(toxicity_rating__lt=settings.TOXICITY_THRESHOLD)

    if request.user.is_authenticated:
        reviews = reviews.annotate(
            sum_votes=Coalesce(Sum("labvote__value"), Value(0)),
            user_vote=Coalesce(
                Sum("labvote__value", filter=Q(labvote__user=request.user)),
                Value(0),
            ),
        )

    reviews = LabReview.sort(reviews, method)
    paginated_reviews = LabReview.paginate(reviews, page_number)

    # Breadcrumbs
    dept = lab.department
    breadcrumbs = [
        ("Labs", reverse("browse") + "?mode=labs", False),
        (dept.school.name, reverse("browse") + "?mode=labs", False),
        (dept.name, reverse("browse") + "?mode=labs", False),
        (lab.pi_name, None, True),
    ]

    # Parse research areas
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
            "mode": "labs",
            "is_lab": True,
        },
    )


@login_required
def lab_upvote(request, review_id):
    """Upvote a lab review."""
    if request.method == "POST":
        review = LabReview.objects.get(pk=review_id)
        review.upvote(request.user)
        return JsonResponse({"ok": True})
    return JsonResponse({"ok": False})


@login_required
def lab_downvote(request, review_id):
    """Downvote a lab review."""
    if request.method == "POST":
        review = LabReview.objects.get(pk=review_id)
        review.downvote(request.user)
        return JsonResponse({"ok": True})
    return JsonResponse({"ok": False})
