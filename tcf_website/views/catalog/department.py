"""Department listing view."""

from django.shortcuts import get_object_or_404, render
from django.urls import reverse

from ...models import Department, Semester
from ...utils import parse_mode


def department(request, dept_id: int, course_recency=None):
    """View for department page - Modern design."""
    dept = get_object_or_404(
        Department.objects.prefetch_related("subdepartment_set"), pk=dept_id
    )

    mode, _ = parse_mode(request)

    breadcrumbs = [
        (dept.school.name, reverse("browse"), False),
        (dept.name, None, True),
    ]

    latest_semester = Semester.latest()

    if latest_semester is None:
        return render(
            request,
            "site/catalog/department.html",
            {
                "mode": mode,
                "dept_id": dept_id,
                "latest_semester": "",
                "breadcrumbs": breadcrumbs,
                "paginated_courses": None,
                "active_course_recency": "",
                "sortby": "course_id",
                "order": "asc",
                "last_five_years": "",
                "no_course_data": True,
            },
        )

    if not course_recency:
        course_recency = str(latest_semester)

    last_five_years = get_object_or_404(Semester, number=latest_semester.number - 50)
    season, year = course_recency.upper().split()
    active_semester = Semester.objects.filter(year=year, season=season).first()

    sortby = request.GET.get("sortby", "course_id")
    order = request.GET.get("order", "asc")
    page = request.GET.get("page", 1)

    paginated_courses = dept.get_paginated_department_courses(
        sortby, latest_semester.year - int(year), order, page
    )

    return render(
        request,
        "site/catalog/department.html",
        {
            "mode": mode,
            "dept_id": dept_id,
            "latest_semester": str(latest_semester),
            "breadcrumbs": breadcrumbs,
            "paginated_courses": paginated_courses,
            "active_course_recency": str(active_semester),
            "sortby": sortby,
            "order": order,
            "last_five_years": str(last_five_years),
        },
    )
