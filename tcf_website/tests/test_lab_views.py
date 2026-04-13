# pylint: disable=no-member
"""Tests for lab views."""

from django.test import TestCase
from django.urls import reverse

from ..models import Department, Lab, School, Semester, User
from .test_utils import suppress_request_warnings


class LabBrowseTestCase(TestCase):
    """Tests for the lab browse page."""

    def setUp(self):
        Semester.objects.create(year=2025, season="SPRING", number=1252)
        self.school = School.objects.create(
            name="School of Engineering & Applied Science"
        )
        self.department = Department.objects.create(
            name="Computer Science", school=self.school
        )
        self.lab = Lab.objects.create(
            pi_name="Test Professor",
            department=self.department,
            research_areas="AI, ML",
            is_recruiting=True,
        )

    def test_browse_labs_200(self):
        """GET /browse/?mode=labs returns 200."""
        response = self.client.get(reverse("browse") + "?mode=labs")
        self.assertEqual(response.status_code, 200)

    def test_browse_labs_contains_lab(self):
        """Browse labs page contains the lab's PI name."""
        response = self.client.get(reverse("browse") + "?mode=labs")
        self.assertContains(response, "Test Professor")


class LabDetailTestCase(TestCase):
    """Tests for the lab detail page."""

    def setUp(self):
        Semester.objects.create(year=2025, season="SPRING", number=1252)
        self.school = School.objects.create(name="Test School")
        self.department = Department.objects.create(
            name="Computer Science", school=self.school
        )
        self.lab = Lab.objects.create(
            pi_name="Jane Doe",
            department=self.department,
            description="Research in AI.",
            research_areas="Artificial Intelligence, Robotics",
            is_recruiting=True,
        )

    def test_lab_detail_200(self):
        """GET /lab/<valid-slug>/ returns 200."""
        response = self.client.get(f"/lab/{self.lab.slug}/")
        self.assertEqual(response.status_code, 200)

    def test_lab_detail_contains_name(self):
        """Lab detail page contains PI name."""
        response = self.client.get(f"/lab/{self.lab.slug}/")
        self.assertContains(response, "Jane Doe")

    def test_lab_detail_contains_research(self):
        """Lab detail page contains research areas."""
        response = self.client.get(f"/lab/{self.lab.slug}/")
        self.assertContains(response, "Artificial Intelligence")

    @suppress_request_warnings
    def test_lab_detail_404(self):
        """GET /lab/<invalid-slug>/ returns 404."""
        response = self.client.get("/lab/nonexistent-slug/")
        self.assertEqual(response.status_code, 404)


class LabSearchTestCase(TestCase):
    """Tests for lab search."""

    def setUp(self):
        Semester.objects.create(year=2025, season="SPRING", number=1252)
        self.school = School.objects.create(name="Engineering")
        self.department = Department.objects.create(
            name="Computer Science", school=self.school
        )
        self.lab = Lab.objects.create(
            pi_name="Computer Vision Prof",
            department=self.department,
            research_areas="Computer Vision, Deep Learning",
        )

    def test_search_labs_200(self):
        """GET /search/?mode=labs&q=computer returns 200."""
        response = self.client.get(reverse("search") + "?mode=labs&q=computer")
        self.assertEqual(response.status_code, 200)


class LoadLabsCommandTestCase(TestCase):
    """Tests for the load_labs management command."""

    def setUp(self):
        self.school = School.objects.create(
            name="School of Engineering & Applied Science"
        )
        Department.objects.create(name="Computer Science", school=self.school)
        Department.objects.create(
            name="Electrical & Computer Engineering", school=self.school
        )

    def test_load_labs_runs(self):
        """load_labs management command runs without error."""
        from django.core.management import call_command
        from io import StringIO

        out = StringIO()
        call_command("load_labs", stdout=out)
        output = out.getvalue()
        self.assertIn("Done:", output)
