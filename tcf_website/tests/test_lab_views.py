# pylint: disable=no-member
"""Tests for lab views."""

from django.test import TestCase, override_settings
from django.urls import reverse

from ..models import Department, Lab, LabReview, School, Semester, User
from .test_utils import suppress_request_warnings


def _make_lab_review(lab, user, **overrides):
    """Build a LabReview with sensible defaults so tests stay terse."""
    defaults = {
        "lab": lab,
        "user": user,
        "overall": 4,
        "mentorship": 4,
        "lab_culture": 4,
        "responsiveness": 4,
        "independence": 4,
        "entry_selectivity": 3,
        "hours_per_week": 10,
        "role": "undergrad_ra",
        "period": "Fall 2024",
        "text": "Solid lab, learned a lot.",
        "would_recommend": True,
    }
    defaults.update(overrides)
    return LabReview.objects.create(**defaults)


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


class LabDetailReviewsTestCase(TestCase):
    """Tests for review handling within the lab_detail view."""

    def setUp(self):
        Semester.objects.create(year=2025, season="SPRING", number=1252)
        self.school = School.objects.create(name="Engineering")
        self.department = Department.objects.create(
            name="CS", school=self.school
        )
        self.lab = Lab.objects.create(
            pi_name="Dr. Pages",
            department=self.department,
        )
        self.author = User.objects.create(
            username="reviewer", computing_id="rev1"
        )

    def _create_n_reviews(self, n, **overrides):
        return [
            _make_lab_review(
                self.lab,
                User.objects.create(username=f"u{i}", computing_id=f"u{i}"),
                **overrides,
            )
            for i in range(n)
        ]

    def test_pagination_first_page_returns_ten(self):
        """With 11 reviews, page 1 surfaces the first 10."""
        self._create_n_reviews(11)
        response = self.client.get(f"/lab/{self.lab.slug}/")
        self.assertEqual(response.status_code, 200)
        page = response.context["paginated_reviews"]
        self.assertEqual(len(page.object_list), 10)
        self.assertTrue(page.has_next())

    def test_pagination_second_page_returns_overflow(self):
        """With 11 reviews, page 2 surfaces the remaining 1."""
        self._create_n_reviews(11)
        response = self.client.get(f"/lab/{self.lab.slug}/?page=2")
        self.assertEqual(response.status_code, 200)
        page = response.context["paginated_reviews"]
        self.assertEqual(len(page.object_list), 1)
        self.assertFalse(page.has_next())

    def test_hidden_reviews_excluded(self):
        """Reviews with hidden=True are not surfaced on lab_detail."""
        _make_lab_review(self.lab, self.author, text="Visible")
        hidden_user = User.objects.create(
            username="ghost", computing_id="g1"
        )
        _make_lab_review(
            self.lab, hidden_user, text="Hidden text", hidden=True
        )
        response = self.client.get(f"/lab/{self.lab.slug}/")
        page = response.context["paginated_reviews"]
        self.assertEqual(len(page.object_list), 1)
        self.assertContains(response, "Visible")
        self.assertNotContains(response, "Hidden text")

    def test_empty_text_reviews_excluded(self):
        """Reviews with empty text are not surfaced on lab_detail."""
        _make_lab_review(self.lab, self.author, text="Has content")
        empty_user = User.objects.create(
            username="silent", computing_id="s1"
        )
        _make_lab_review(self.lab, empty_user, text="")
        response = self.client.get(f"/lab/{self.lab.slug}/")
        page = response.context["paginated_reviews"]
        self.assertEqual(len(page.object_list), 1)

    @override_settings(TOXICITY_THRESHOLD=50)
    def test_toxic_reviews_filtered_when_threshold_set(self):
        """Reviews with toxicity_rating >= TOXICITY_THRESHOLD are excluded."""
        _make_lab_review(
            self.lab, self.author, text="Clean", toxicity_rating=10
        )
        toxic_user = User.objects.create(
            username="rude", computing_id="r1"
        )
        _make_lab_review(
            self.lab, toxic_user, text="Toxic", toxicity_rating=80
        )
        response = self.client.get(f"/lab/{self.lab.slug}/")
        page = response.context["paginated_reviews"]
        self.assertEqual(len(page.object_list), 1)
        self.assertContains(response, "Clean")
        self.assertNotContains(response, "Toxic")

    def test_bar_widths_scale_ratings_to_percent(self):
        """bar_widths multiplies each rating by 20 (1-5 scale to 0-100%)."""
        _make_lab_review(
            self.lab,
            self.author,
            mentorship=5,
            lab_culture=4,
            responsiveness=3,
            independence=2,
            entry_selectivity=1,
        )
        response = self.client.get(f"/lab/{self.lab.slug}/")
        bar_widths = response.context["bar_widths"]
        self.assertEqual(bar_widths["mentorship"], 100.0)
        self.assertEqual(bar_widths["lab_culture"], 80.0)
        self.assertEqual(bar_widths["responsiveness"], 60.0)
        self.assertEqual(bar_widths["independence"], 40.0)
        self.assertEqual(bar_widths["entry_selectivity"], 20.0)

    def test_bar_widths_zero_when_no_reviews(self):
        """bar_widths defaults to 0 when there are no reviews to average."""
        response = self.client.get(f"/lab/{self.lab.slug}/")
        bar_widths = response.context["bar_widths"]
        for key in (
            "mentorship",
            "lab_culture",
            "responsiveness",
            "independence",
            "entry_selectivity",
        ):
            self.assertEqual(bar_widths[key], 0)

    def test_recommend_pct_aggregates_correctly(self):
        """recommend_pct counts would_recommend=True over total."""
        users = [
            User.objects.create(username=f"r{i}", computing_id=f"rp{i}")
            for i in range(4)
        ]
        _make_lab_review(self.lab, users[0], would_recommend=True)
        _make_lab_review(self.lab, users[1], would_recommend=True)
        _make_lab_review(self.lab, users[2], would_recommend=True)
        _make_lab_review(self.lab, users[3], would_recommend=False)
        response = self.client.get(f"/lab/{self.lab.slug}/")
        self.assertEqual(response.context["recommend_pct"], 75)
        self.assertEqual(response.context["review_count"], 4)

    def test_vote_context_annotates_authenticated_user(self):
        """Authenticated requests get sum_votes/user_vote annotations."""
        review = _make_lab_review(self.lab, self.author)
        voter = User.objects.create(
            username="voter", computing_id="v1", password="x"
        )
        voter.set_password("x")
        voter.save()
        review.upvote(voter)

        self.client.force_login(voter)
        response = self.client.get(f"/lab/{self.lab.slug}/")
        page = response.context["paginated_reviews"]
        annotated = page.object_list[0]
        self.assertEqual(annotated.sum_votes, 1)
        self.assertEqual(annotated.user_vote, 1)

    def test_anonymous_request_has_no_vote_annotations(self):
        """Anonymous requests skip the auth-only annotations."""
        _make_lab_review(self.lab, self.author)
        response = self.client.get(f"/lab/{self.lab.slug}/")
        page = response.context["paginated_reviews"]
        review = page.object_list[0]
        self.assertFalse(hasattr(review, "user_vote"))


class LabDepartmentTestCase(TestCase):
    """Tests for the lab_department view."""

    def setUp(self):
        Semester.objects.create(year=2025, season="SPRING", number=1252)
        self.school = School.objects.create(
            name="School of Engineering & Applied Science"
        )
        self.department = Department.objects.create(
            name="Computer Science", school=self.school
        )
        self.other_department = Department.objects.create(
            name="Civil Engineering", school=self.school
        )
        self.lab_a = Lab.objects.create(
            pi_name="Alice Smith",
            department=self.department,
            is_recruiting=False,
        )
        self.lab_b = Lab.objects.create(
            pi_name="Bob Jones",
            department=self.department,
            is_recruiting=True,
        )
        self.lab_other = Lab.objects.create(
            pi_name="Different Dept",
            department=self.other_department,
        )

    def test_lab_department_returns_200(self):
        """GET /lab-department/<dept_id>/ returns 200."""
        response = self.client.get(
            reverse("lab_department", args=[self.department.id])
        )
        self.assertEqual(response.status_code, 200)

    def test_lab_department_filters_by_department(self):
        """Only labs in the requested department are listed."""
        response = self.client.get(
            reverse("lab_department", args=[self.department.id])
        )
        labs = list(response.context["labs"])
        self.assertEqual(len(labs), 2)
        self.assertNotIn(self.lab_other, labs)

    def test_lab_department_orders_recruiting_first(self):
        """Recruiting labs surface before non-recruiting; then by pi_name."""
        response = self.client.get(
            reverse("lab_department", args=[self.department.id])
        )
        labs = list(response.context["labs"])
        self.assertEqual(labs[0].pi_name, "Bob Jones")
        self.assertEqual(labs[1].pi_name, "Alice Smith")

    def test_lab_department_breadcrumbs_include_school_and_dept(self):
        """Breadcrumbs trail school -> department."""
        response = self.client.get(
            reverse("lab_department", args=[self.department.id])
        )
        breadcrumb_labels = [b[0] for b in response.context["breadcrumbs"]]
        self.assertIn(self.school.name, breadcrumb_labels)
        self.assertIn(self.department.name, breadcrumb_labels)
