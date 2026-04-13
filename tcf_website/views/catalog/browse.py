"""Browse landing page (course catalog vs clubs) and advanced search."""

from django.db.models import Prefetch
from django.http import HttpResponse
from django.shortcuts import render

from ...forms import AdvancedSearchForm, ClubAdvancedSearchForm, LabSearchForm
from ...models import Club, ClubCategory, Department, Lab, School
from ...search.browse_helpers import (
    advanced_search_results_payload,
    club_advanced_search_results_payload,
    is_browse_results_partial_request,
)
from ...utils import parse_mode


def _browse_clubs(request, mode: str):
    """Clubs browse: category grid and/or filtered results."""
    club_form = ClubAdvancedSearchForm(request.GET or None)
    has_search = club_form.is_bound and club_form.has_search_params()

    if is_browse_results_partial_request(request):
        if not has_search:
            return HttpResponse(status=204)
        payload = club_advanced_search_results_payload(request, club_form)
        return render(
            request,
            "site/catalog/partials/_browse_club_advanced_results.html",
            {"request": request, **payload},
        )

    club_categories = (
        ClubCategory.objects.all()
        .prefetch_related(
            Prefetch(
                "club_set",
                queryset=Club.objects.order_by("name"),
                to_attr="clubs",
            )
        )
        .order_by("name")
    )

    if has_search:
        payload = club_advanced_search_results_payload(request, club_form)
        return render(
            request,
            "site/catalog/browse.html",
            {
                "is_club": True,
                "mode": mode,
                "club_form": club_form,
                "has_search": True,
                "club_categories": club_categories,
                **payload,
            },
        )

    return render(
        request,
        "site/catalog/browse.html",
        {
            "is_club": True,
            "mode": mode,
            "club_form": club_form if club_form.is_bound else ClubAdvancedSearchForm(),
            "has_search": False,
            "club_categories": club_categories,
        },
    )


def _browse_courses(request, mode: str):
    """Courses browse: schools grid and/or advanced search results."""
    form = AdvancedSearchForm(request.GET or None)
    has_search = form.is_bound and form.has_search_params()

    if is_browse_results_partial_request(request):
        if not has_search:
            return HttpResponse(status=204)
        payload = advanced_search_results_payload(request, form)
        return render(
            request,
            "site/catalog/partials/_browse_advanced_results.html",
            {"request": request, **payload},
        )

    if has_search:
        payload = advanced_search_results_payload(request, form)
        return render(
            request,
            "site/catalog/browse.html",
            {
                "is_club": False,
                "mode": mode,
                "form": form,
                "has_search": True,
                **payload,
            },
        )

    featured = {
        s.name: s
        for s in School.objects.filter(
            name__in=[
                "College of Arts & Sciences",
                "School of Engineering & Applied Science",
            ]
        )
    }
    clas = featured.get("College of Arts & Sciences")
    seas = featured.get("School of Engineering & Applied Science")

    excluded_list = [s.pk for s in [clas, seas] if s is not None]
    other_schools = School.objects.exclude(pk__in=excluded_list).order_by("name")

    return render(
        request,
        "site/catalog/browse.html",
        {
            "is_club": False,
            "mode": mode,
            "form": form if form.is_bound else AdvancedSearchForm(),
            "has_search": False,
            "CLAS": clas,
            "SEAS": seas,
            "other_schools": other_schools,
        },
    )


def _browse_labs(request, mode: str):
    """Labs browse: search form + schools/departments grid."""
    lab_form = LabSearchForm(request.GET or None)
    has_search = lab_form.is_bound and lab_form.has_search_params()

    # Only show recruiting labs — students want labs they can actually join
    labs_qs = Lab.objects.filter(is_recruiting=True)
    if has_search and lab_form.is_valid():
        data = lab_form.cleaned_data
        if data.get("q"):
            q = data["q"].strip()
            labs_qs = labs_qs.filter(combined_search_text__icontains=q)
        if data.get("department"):
            labs_qs = labs_qs.filter(department_id=data["department"])

    schools = (
        School.objects.filter(department__lab__in=labs_qs)
        .distinct()
        .prefetch_related(
            Prefetch(
                "department_set",
                queryset=Department.objects.filter(lab__in=labs_qs)
                .distinct()
                .prefetch_related(
                    Prefetch(
                        "lab_set",
                        queryset=labs_qs.order_by("pi_name"),
                        to_attr="labs",
                    )
                )
                .order_by("name"),
                to_attr="departments_with_labs",
            )
        )
        .order_by("name")
    )

    return render(
        request,
        "site/catalog/browse.html",
        {
            "is_club": False,
            "is_lab": True,
            "mode": mode,
            "lab_form": lab_form if lab_form.is_bound else LabSearchForm(),
            "has_search": has_search,
            "lab_schools": schools,
        },
    )


def browse(request):
    """View for browse page with advanced course or club search."""
    mode, is_club = parse_mode(request)
    is_lab = mode == "labs"
    if is_club:
        return _browse_clubs(request, mode)
    if is_lab:
        return _browse_labs(request, mode)
    return _browse_courses(request, mode)
