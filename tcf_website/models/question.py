# pylint: disable=missing-class-docstring, fixme, line-too-long, unused-import, no-member
"""TCF question models."""

from django.conf import settings
from django.contrib.postgres.aggregates.general import ArrayAgg
from django.contrib.postgres.indexes import GinIndex
from django.core.paginator import EmptyPage, Page, PageNotAnInteger, Paginator
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import (
    Avg,
    Case,
    CharField,
    Exists,
    ExpressionWrapper,
    F,
    FloatField,
    IntegerField,
    OuterRef,
    Q,
    QuerySet,
    Subquery,
    Sum,
    Value,
    When,
    fields,
)
from django.db.models.functions import Abs, Coalesce, Concat, Round

from .user import User


class Question(models.Model):
    """Question model.
    Belongs to a User.
    Has a course and instructor.
    """

    text = models.TextField()
    course = models.ForeignKey("Course", on_delete=models.CASCADE)
    instructor = models.ForeignKey("Instructor", on_delete=models.CASCADE, default=None)
    user = models.ForeignKey("User", on_delete=models.CASCADE)
    created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Question for {self.course}"

    def count_votes(self):
        """Sum votes for review."""
        return self.votequestion_set.aggregate(
            upvotes=Coalesce(models.Sum("value", filter=models.Q(value=1)), 0),
            downvotes=Coalesce(Abs(models.Sum("value", filter=models.Q(value=-1))), 0),
        )

    def upvote(self, user):
        """Create an upvote."""

        # Check if already upvoted.
        upvoted = VoteQuestion.objects.filter(
            user=user,
            question=self,
            value=1,
        ).exists()

        # Delete all prior votes.
        VoteQuestion.objects.filter(
            user=user,
            question=self,
        ).delete()

        # Don't upvote again if previously upvoted.
        if upvoted:
            return

        VoteQuestion.objects.create(
            value=1,
            user=user,
            question=self,
        )

    def downvote(self, user):
        """Create a downvote."""

        # Check if already downvoted.
        downvoted = VoteQuestion.objects.filter(
            user=user,
            question=self,
            value=-1,
        ).exists()

        # Delete all prior votes.
        VoteQuestion.objects.filter(
            user=user,
            question=self,
        ).delete()

        # Don't downvote again if previously downvoted.
        if downvoted:
            return

        VoteQuestion.objects.create(
            value=-1,
            user=user,
            question=self,
        )

    @staticmethod
    def display_activity(course_id, instructor_id, user):
        """Prepare review list for course-instructor page."""
        question = (
            Question.objects.filter(instructor=instructor_id, course=course_id)
            .exclude(text="")
            .annotate(
                sum_q_votes=models.functions.Coalesce(
                    models.Sum("votequestion__value"), models.Value(0)
                ),
            )
        )
        if user.is_authenticated:
            question = question.annotate(
                user_q_vote=models.functions.Coalesce(
                    models.Sum(
                        "votequestion__value",
                        filter=models.Q(votequestion__user=user),
                    ),
                    models.Value(0),
                ),
            )
        return question.order_by("-created")


class Answer(models.Model):
    """Answer model.
    Belongs to a User.
    Has a question.
    """

    text = models.TextField()
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    user = models.ForeignKey("User", on_delete=models.CASCADE)
    created = models.DateTimeField(auto_now_add=True)
    semester = models.ForeignKey("Semester", on_delete=models.CASCADE, default=None)

    def __str__(self):
        return f"Answer for {self.question}"

    def count_votes(self):
        """Sum votes for answers."""
        return self.voteanswer_set.aggregate(
            upvotes=Coalesce(models.Sum("value", filter=models.Q(value=1)), 0),
            downvotes=Coalesce(Abs(models.Sum("value", filter=models.Q(value=-1))), 0),
        )

    def upvote(self, user):
        """Create an upvote."""

        # Check if already upvoted.
        upvoted = VoteAnswer.objects.filter(
            user=user,
            answer=self,
            value=1,
        ).exists()

        # Delete all prior votes.
        VoteAnswer.objects.filter(
            user=user,
            answer=self,
        ).delete()

        # Don't upvote again if previously upvoted.
        if upvoted:
            return

        VoteAnswer.objects.create(
            value=1,
            user=user,
            answer=self,
        )

    def downvote(self, user):
        """Create a downvote."""

        # Check if already downvoted.
        downvoted = VoteAnswer.objects.filter(
            user=user,
            answer=self,
            value=-1,
        ).exists()

        # Delete all prior votes.
        VoteAnswer.objects.filter(
            user=user,
            answer=self,
        ).delete()

        # Don't downvote again if previously downvoted.
        if downvoted:
            return

        VoteAnswer.objects.create(
            value=-1,
            user=user,
            answer=self,
        )

    @staticmethod
    def display_activity(question_id, user):
        """Prepare answers for course-instructor page."""
        answer = (
            Answer.objects.filter(question=question_id)
            .exclude(text="")
            .annotate(
                sum_a_votes=models.functions.Coalesce(
                    models.Sum("voteanswer__value"), models.Value(0)
                ),
            )
        )
        if user.is_authenticated:
            answer = answer.annotate(
                user_a_vote=models.functions.Coalesce(
                    models.Sum(
                        "voteanswer__value",
                        filter=models.Q(voteanswer__user=user),
                    ),
                    models.Value(0),
                ),
            )
        return answer.order_by("-created")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "question"],
                name="unique answer per user and question",
            )
        ]


class VoteQuestion(models.Model):
    """Vote model.

    Belongs to a User.
    Has a question.
    """

    # Vote value. Required.
    value = models.IntegerField(
        validators=[MinValueValidator(-1), MaxValueValidator(1)]
    )
    # Vote user foreign key. Required.
    user = models.ForeignKey("User", on_delete=models.CASCADE)
    # Vote question foreign key. Required.
    question = models.ForeignKey(Question, on_delete=models.CASCADE)

    def __str__(self):
        return f"Vote of value {self.value} for {self.question} by {self.user}"

    class Meta:
        indexes = [
            models.Index(fields=["question"]),
        ]

        constraints = [
            models.UniqueConstraint(
                fields=["user", "question"],
                name="unique vote per user and question",
            )
        ]


class VoteAnswer(models.Model):
    """Vote model.

    Belongs to a User.
    Has a question.
    """

    # Vote value. Required.
    value = models.IntegerField(
        validators=[MinValueValidator(-1), MaxValueValidator(1)]
    )
    # Vote user foreign key. Required.
    user = models.ForeignKey("User", on_delete=models.CASCADE)
    # Vote answer foreign key. Required.
    answer = models.ForeignKey(Answer, on_delete=models.CASCADE)

    def __str__(self):
        return f"Vote of value {self.value} for {self.answer} by {self.user}"

    class Meta:
        indexes = [
            models.Index(fields=["answer"]),
        ]

        constraints = [
            models.UniqueConstraint(
                fields=["user", "answer"],
                name="unique vote per user and answer",
            )
        ]
