# pylint: disable=no-member
"""Parity tests for the Votable mixin.

Exercises upvote/downvote/count_votes uniformly across every concrete
subclass (Review, LabReview, Question, Answer) to confirm the abstract
behavior is identical regardless of which vote table backs the object.

How the test suite is organized
-------------------------------
The pattern here is design-by-contract:

1. ``_VotableContractMixin`` defines seven behavioral checks every
   Votable subclass must satisfy: starting at zero votes, single
   upvote/downvote, toggle-off on re-vote, replace upvote with
   downvote, aggregation across multiple users.
2. Each concrete subclass under test (Review, LabReview, Question,
   Answer) gets its own ``TestCase`` that inherits both
   ``_VotableContractMixin`` and ``django.test.TestCase``. The
   subclass only writes ``setUp`` to build the object under test
   and assigns it to ``self.target``.
3. Django's test runner discovers each TestCase, runs all seven
   inherited checks against that subclass's ``self.target``, and
   reports per-class results. Total: 7 checks x 4 subclasses = 28
   independent test runs from one suite of assertions.

To add a fifth Votable-using class later, add a new TestCase that
inherits the mixin and writes ``setUp``. No assertions need to be
copied or maintained.
"""

from django.test import TestCase

from ..models import (
    Answer,
    Course,
    Department,
    Instructor,
    Lab,
    LabReview,
    Question,
    Review,
    School,
    Semester,
    Subdepartment,
    User,
)


def _make_users(n=2):
    return [
        User.objects.create(username=f"voter{i}", computing_id=f"v{i}")
        for i in range(n)
    ]


class _VotableContractMixin:
    """Shared assertions every Votable subclass must satisfy.

    Subclasses provide ``self.target`` (the votable instance) in
    ``setUp`` and run the same suite of behavioral checks against it.
    The leading underscore signals this is a test-helper base, not a
    concrete TestCase the runner should pick up directly.
    """

    target = None  # set by subclass setUp

    def test_count_votes_starts_zero(self):
        counts = self.target.count_votes()
        self.assertEqual(counts["upvotes"], 0)
        self.assertEqual(counts["downvotes"], 0)

    def test_upvote_increments(self):
        user = _make_users(1)[0]
        self.target.upvote(user)
        counts = self.target.count_votes()
        self.assertEqual(counts["upvotes"], 1)
        self.assertEqual(counts["downvotes"], 0)

    def test_downvote_increments(self):
        user = _make_users(1)[0]
        self.target.downvote(user)
        counts = self.target.count_votes()
        self.assertEqual(counts["upvotes"], 0)
        self.assertEqual(counts["downvotes"], 1)

    def test_upvote_twice_same_user_toggles_off(self):
        user = _make_users(1)[0]
        self.target.upvote(user)
        self.target.upvote(user)
        counts = self.target.count_votes()
        self.assertEqual(counts["upvotes"], 0)
        self.assertEqual(counts["downvotes"], 0)

    def test_downvote_twice_same_user_toggles_off(self):
        user = _make_users(1)[0]
        self.target.downvote(user)
        self.target.downvote(user)
        counts = self.target.count_votes()
        self.assertEqual(counts["upvotes"], 0)
        self.assertEqual(counts["downvotes"], 0)

    def test_upvote_then_downvote_replaces(self):
        user = _make_users(1)[0]
        self.target.upvote(user)
        self.target.downvote(user)
        counts = self.target.count_votes()
        self.assertEqual(counts["upvotes"], 0)
        self.assertEqual(counts["downvotes"], 1)

    def test_aggregation_across_users(self):
        users = _make_users(3)
        self.target.upvote(users[0])
        self.target.upvote(users[1])
        self.target.downvote(users[2])
        counts = self.target.count_votes()
        self.assertEqual(counts["upvotes"], 2)
        self.assertEqual(counts["downvotes"], 1)


def _course_fixture():
    """Build the course/instructor/semester graph Review/Question need."""
    school = School.objects.create(name="Test School")
    department = Department.objects.create(name="CS", school=school)
    subdept = Subdepartment.objects.create(
        name="Computer Science", mnemonic="CS", department=department
    )
    semester = Semester.objects.create(year=2025, season="SPRING", number=1252)
    course = Course.objects.create(
        title="Intro to CS",
        number=1110,
        subdepartment=subdept,
        semester_last_taught=semester,
    )
    instructor = Instructor.objects.create(
        first_name="Test", last_name="Prof", email="prof@test.edu"
    )
    return semester, course, instructor


class ReviewVotableTestCase(_VotableContractMixin, TestCase):
    def setUp(self):
        author = User.objects.create(username="author", computing_id="a1")
        semester, course, instructor = _course_fixture()
        self.target = Review.objects.create(
            text="Test review",
            user=author,
            course=course,
            instructor=instructor,
            semester=semester,
            instructor_rating=4,
            difficulty=3,
            recommendability=5,
            enjoyability=4,
            hours_per_week=5,
            amount_reading=1,
            amount_writing=1,
            amount_group=1,
            amount_homework=1,
        )


class LabReviewVotableTestCase(_VotableContractMixin, TestCase):
    def setUp(self):
        author = User.objects.create(username="lab_author", computing_id="la1")
        school = School.objects.create(name="SEAS")
        department = Department.objects.create(name="CS", school=school)
        lab = Lab.objects.create(pi_name="Dr. Test", department=department)
        self.target = LabReview.objects.create(
            text="Test lab review",
            user=author,
            lab=lab,
            overall=4,
            mentorship=4,
            lab_culture=4,
            responsiveness=4,
            independence=4,
            entry_selectivity=3,
            hours_per_week=10,
        )


class QuestionVotableTestCase(_VotableContractMixin, TestCase):
    def setUp(self):
        author = User.objects.create(username="asker", computing_id="q1")
        _, course, instructor = _course_fixture()
        self.target = Question.objects.create(
            text="Test question",
            user=author,
            course=course,
            instructor=instructor,
        )


class AnswerVotableTestCase(_VotableContractMixin, TestCase):
    def setUp(self):
        author = User.objects.create(username="answerer", computing_id="ans1")
        semester, course, instructor = _course_fixture()
        question = Question.objects.create(
            text="Q?",
            user=author,
            course=course,
            instructor=instructor,
        )
        self.target = Answer.objects.create(
            text="Test answer",
            user=author,
            question=question,
            semester=semester,
        )
