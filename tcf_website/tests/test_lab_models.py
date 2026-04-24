# pylint: disable=no-member
"""Tests for Lab, LabReview, and LabVote models."""

from django.db import IntegrityError
from django.test import TestCase

from ..models import Department, Lab, LabReview, LabVote, School, User


class LabModelTestCase(TestCase):
    """Tests for the Lab model."""

    def setUp(self):
        self.school = School.objects.create(name="Test Engineering School")
        self.department = Department.objects.create(
            name="Computer Science", school=self.school
        )
        self.user = User.objects.create(
            username="testuser", computing_id="test123"
        )

    def test_save_generates_slug(self):
        """Lab.save() auto-generates slug from pi_name."""
        lab = Lab.objects.create(
            pi_name="John Doe",
            department=self.department,
        )
        self.assertEqual(lab.slug, "john-doe")

    def test_save_handles_slug_collision(self):
        """Lab.save() appends -2 on slug collision."""
        Lab.objects.create(
            pi_name="John Doe",
            department=self.department,
        )
        lab2 = Lab.objects.create(
            pi_name="John Doe",
            department=self.department,
            slug="",  # Force regeneration
        )
        self.assertEqual(lab2.slug, "john-doe-2")

    def test_save_computes_combined_search_text(self):
        """Lab.save() populates combined_search_text."""
        lab = Lab.objects.create(
            pi_name="Jane Smith",
            department=self.department,
            research_areas="Machine Learning, NLP",
        )
        self.assertIn("Jane Smith", lab.combined_search_text)
        self.assertIn("Machine Learning", lab.combined_search_text)
        self.assertIn("Computer Science", lab.combined_search_text)

    def test_avg_ratings_empty(self):
        """avg_ratings returns None values when no reviews exist."""
        lab = Lab.objects.create(pi_name="Empty Lab", department=self.department)
        stats = lab.avg_ratings()
        self.assertIsNone(stats["overall"])
        self.assertIsNone(stats["mentorship"])

    def test_avg_ratings_with_reviews(self):
        """avg_ratings computes correct averages."""
        lab = Lab.objects.create(pi_name="Rated Lab", department=self.department)
        LabReview.objects.create(
            lab=lab, user=self.user, overall=4, mentorship=5,
            independence=3, lab_culture=4, entry_selectivity=2, responsiveness=3,
            hours_per_week=10, role="undergrad_ra", period="Fall 2024",
        )
        stats = lab.avg_ratings()
        self.assertEqual(stats["overall"], 4.0)
        self.assertEqual(stats["mentorship"], 5.0)
        self.assertEqual(stats["independence"], 3.0)
        self.assertEqual(stats["lab_culture"], 4.0)
        self.assertEqual(stats["entry_selectivity"], 2.0)

    def test_str(self):
        """Test __str__ method in Lab model."""
        lab = Lab.objects.create(pi_name="Test PI", department=self.department)
        self.assertEqual(str(lab), "Test PI")


class LabReviewTestCase(TestCase):
    """Tests for the LabReview model."""

    def setUp(self):
        self.school = School.objects.create(name="Test School")
        self.department = Department.objects.create(
            name="Engineering", school=self.school
        )
        self.lab = Lab.objects.create(
            pi_name="Test PI", department=self.department
        )
        self.user1 = User.objects.create(
            username="reviewer1", computing_id="rev1"
        )
        self.user2 = User.objects.create(
            username="reviewer2", computing_id="rev2"
        )
        self.review = LabReview.objects.create(
            lab=self.lab, user=self.user1, overall=4, mentorship=3,
            independence=4, lab_culture=5, entry_selectivity=2, responsiveness=3,
            hours_per_week=15, role="undergrad_ra", period="Spring 2025",
            text="Great lab.",
        )

    def test_upvote(self):
        """Upvoting creates a LabVote with value=1."""
        self.review.upvote(self.user2)
        vote = LabVote.objects.get(user=self.user2, review=self.review)
        self.assertEqual(vote.value, 1)

    def test_upvote_toggle(self):
        """Upvoting twice removes the vote."""
        self.review.upvote(self.user2)
        self.review.upvote(self.user2)
        self.assertFalse(
            LabVote.objects.filter(user=self.user2, review=self.review).exists()
        )

    def test_downvote(self):
        """Downvoting creates a LabVote with value=-1."""
        self.review.downvote(self.user2)
        vote = LabVote.objects.get(user=self.user2, review=self.review)
        self.assertEqual(vote.value, -1)

    def test_count_votes(self):
        """count_votes returns correct upvote/downvote counts."""
        self.review.upvote(self.user1)
        self.review.downvote(self.user2)
        counts = self.review.count_votes()
        self.assertEqual(counts["upvotes"], 1)
        self.assertEqual(counts["downvotes"], 1)

    def test_sort_most_recent(self):
        """sort with 'Most Recent' orders by -created."""
        review2 = LabReview.objects.create(
            lab=self.lab, user=self.user2, overall=5, mentorship=5,
            independence=5, lab_culture=5, entry_selectivity=3, responsiveness=5,
            hours_per_week=5, role="grad_ra", period="Fall 2024",
            text="Amazing.",
        )
        qs = LabReview.objects.filter(lab=self.lab)
        sorted_qs = LabReview.sort(qs, "Most Recent")
        self.assertEqual(sorted_qs.first(), review2)


class LabVoteTestCase(TestCase):
    """Tests for the LabVote unique constraint."""

    def setUp(self):
        self.school = School.objects.create(name="Vote School")
        self.department = Department.objects.create(
            name="CS", school=self.school
        )
        self.lab = Lab.objects.create(
            pi_name="Vote PI", department=self.department
        )
        self.user = User.objects.create(
            username="voter", computing_id="voter1"
        )
        self.review = LabReview.objects.create(
            lab=self.lab, user=self.user, overall=3, mentorship=3,
            independence=3, lab_culture=3, entry_selectivity=2, responsiveness=3,
            hours_per_week=10, role="other", period="2024",
        )

    def test_unique_constraint(self):
        """Cannot create two votes by same user on same review."""
        LabVote.objects.create(value=1, user=self.user, review=self.review)
        with self.assertRaises(IntegrityError):
            LabVote.objects.create(value=-1, user=self.user, review=self.review)


class LabReviewDefaultsAndStrTestCase(TestCase):
    """Defaults, __str__ format, and ordering edge cases on LabReview."""

    def setUp(self):
        self.school = School.objects.create(name="Engineering")
        self.department = Department.objects.create(
            name="CS", school=self.school
        )
        self.lab = Lab.objects.create(
            pi_name="Default Tester", department=self.department
        )
        self.user = User.objects.create(
            username="defaults_user", computing_id="def1"
        )

    def _build(self, **overrides):
        kwargs = {
            "lab": self.lab,
            "user": self.user,
            "overall": 3,
            "mentorship": 3,
            "lab_culture": 3,
            "responsiveness": 3,
            "independence": 3,
            "entry_selectivity": 3,
            "hours_per_week": 5,
            "role": "undergrad_ra",
            "period": "Spring 2025",
        }
        kwargs.update(overrides)
        return LabReview.objects.create(**kwargs)

    def test_would_recommend_defaults_true(self):
        """LabReview.would_recommend defaults to True when not provided."""
        review = self._build()
        self.assertTrue(review.would_recommend)

    def test_hidden_defaults_false(self):
        """LabReview.hidden defaults to False so reviews are visible."""
        review = self._build()
        self.assertFalse(review.hidden)

    def test_toxicity_rating_defaults_zero(self):
        """LabReview.toxicity_rating defaults to 0 (clean)."""
        review = self._build()
        self.assertEqual(review.toxicity_rating, 0)

    def test_text_defaults_empty(self):
        """LabReview.text is optional and defaults to empty string."""
        review = self._build()
        self.assertEqual(review.text, "")

    def test_str_format(self):
        """__str__ uses 'Lab review by <user> for <lab>'."""
        review = self._build()
        rendered = str(review)
        self.assertIn("Lab review by", rendered)
        self.assertIn(str(self.user), rendered)
        self.assertIn(str(self.lab), rendered)

    def test_ordering_stable_on_tied_vote_counts(self):
        """Sort('Most Helpful') with tied vote counts returns all reviews
        in a deterministic order without crashing."""
        users = [
            User.objects.create(username=f"o{i}", computing_id=f"ord{i}")
            for i in range(3)
        ]
        reviews = [
            self._build(user=users[i], hours_per_week=i + 1) for i in range(3)
        ]
        sorted_qs = LabReview.sort(LabReview.objects.all(), "Most Helpful")
        result_ids = list(sorted_qs.values_list("id", flat=True))
        self.assertEqual(set(result_ids), {r.id for r in reviews})
