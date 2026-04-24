# pylint: disable=missing-class-docstring, fixme, line-too-long, unused-import, no-member, cyclic-import
"""TCF review models."""

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

from tcf_website.pagination import paginate

from .course import Course, Instructor, Semester
from .mixins import Votable
from .user import User


class Review(Votable):
    """Review model.

    Belongs to a User.
    Has a Course.
    Has an Instructor.
    Has an Semester.
    Can optionally have a Club instead of a Course.
    """

    # Review text. Optional.
    text = models.TextField(blank=True)
    # Review user foreign key. Required.
    user = models.ForeignKey("User", on_delete=models.CASCADE)
    # Review course foreign key. Required only if club is not provided.
    course = models.ForeignKey("Course", on_delete=models.CASCADE, null=True, blank=True)
    # Review club foreign key. Optional alternative to course.
    club = models.ForeignKey("Club", on_delete=models.CASCADE, null=True, blank=True)
    # Review instructor foreign key. Required only if club is not provided.
    instructor = models.ForeignKey("Instructor", on_delete=models.CASCADE, null=True, blank=True
    )
    # Review semester foreign key. Required.
    semester = models.ForeignKey("Semester", on_delete=models.CASCADE)
    # Email of reviewer for Review Drive, should be blank most of the time
    # Only done for reviews without accounts
    email = models.CharField(default="", null=True, blank=True)
    # Toxicity rating of review
    toxicity_rating = models.IntegerField(default=0)
    # Most relevant toxicity category, only exists if review has text
    toxicity_category = models.CharField(blank=True)

    # Enum of Rating options.
    RATINGS = (
        (1, 1),
        (2, 2),
        (3, 3),
        (4, 4),
        (5, 5),
    )
    # Review instructor rating. Required.
    instructor_rating = models.PositiveSmallIntegerField(choices=RATINGS)
    # Review difficulty. Required.
    difficulty = models.PositiveSmallIntegerField(choices=RATINGS)
    # Review recommendability. Required.
    recommendability = models.PositiveSmallIntegerField(choices=RATINGS)
    # Review enjoyability. Required.
    enjoyability = models.PositiveSmallIntegerField(choices=RATINGS)

    # Review hours per week. Required.
    # hours_per_week used to be the only thing, but we also brought back the
    # subcategories. This is just a sum, but I'm keeping it because other parts
    # of the codebase depend on this model field existing and I'm not fixing them.
    # TODO: make validators/tests to ensure hours_per_week is the sum, or just
    #  remove it entirely from the model and replace w/ function
    hours_per_week = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(80)]
    )
    # Review hours of reading per week. Required.
    amount_reading = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(20)]
    )
    # Review hours of writing per week. Required.
    amount_writing = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(20)]
    )
    # Review hours of group work per week. Required.
    amount_group = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(20)]
    )
    # Review hours of homework per week. Required.
    amount_homework = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(20)]
    )

    # Review created date. Required.
    created = models.DateTimeField(auto_now_add=True)
    # Review modified date. Required.
    modified = models.DateTimeField(auto_now=True)

    # Review visibility. Required. Default visible.
    hidden = models.BooleanField(default=False)

    # does this get used anywhere? not sure
    def average(self):
        """Average score for review."""
        return (self.instructor_rating + self.recommendability + self.enjoyability) / 3

    @property
    def _vote_manager(self):
        """Return the reverse manager pointing at this object's vote table."""
        return self.vote_set

    @staticmethod
    def get_sorted_reviews(course_id, instructor_id, user, method=""):
        """Prepare review list for course-instructor page."""

        # Filter out reviews that are hidden, have no text, or are toxic.
        reviews = (
            Review.objects.filter(
                instructor=instructor_id,
                course=course_id,
                toxicity_rating__lt=settings.TOXICITY_THRESHOLD,
                hidden=False,
            )
            .exclude(text="")
            .annotate(
                sum_votes=models.functions.Coalesce(
                    models.Sum("vote__value"), models.Value(0)
                ),
            )
        )

        if user.is_authenticated:
            reviews = reviews.annotate(
                user_vote=models.functions.Coalesce(
                    models.Sum("vote__value", filter=models.Q(vote__user=user)),
                    models.Value(0),
                ),
            )

        return Review.sort(reviews, method)

    @staticmethod
    def _annotate_average(reviews):
        """Annotate reviews with the average of the three rating fields."""
        return reviews.annotate(
            average=ExpressionWrapper(
                (F("instructor_rating") + F("recommendability") + F("enjoyability"))
                / 3,
                output_field=fields.FloatField(),
            )
        )

    @staticmethod
    def sort(reviews: "QuerySet[Review]", method="") -> "QuerySet[Review]":
        """Sort reviews by given method - upvotes, rating (low or high), or recent."""
        match method:
            case "Most Helpful":  # net votes
                return reviews.annotate(
                    upvotes=Coalesce(Sum("vote__value", filter=Q(vote__value=1)), 0),
                    downvotes=Coalesce(
                        Abs(Sum("vote__value", filter=Q(vote__value=-1))), 0
                    ),
                    helpful_score=ExpressionWrapper(
                        F("upvotes") - F("downvotes"),
                        output_field=fields.IntegerField(),
                    ),
                ).order_by("-helpful_score")
            case "Highest Rating":
                return Review._annotate_average(reviews).order_by("-average")
            case "Lowest Rating":
                return Review._annotate_average(reviews).order_by("average")
            case "Most Recent":
                return reviews.order_by("-created")
            case "Default" | _:
                return reviews.order_by("-created")

    @staticmethod
    def get_paginated_reviews(
        course_id, instructor_id, user, page_number=1, method=""
    ) -> "Page[Review]":
        """Generate sorted, paginated reviews"""
        reviews = Review.get_sorted_reviews(course_id, instructor_id, user, method)
        return paginate(reviews, page_number)

    def __str__(self):
        """Return human-readable representation of Review."""
        return f"Review by {self.user} for {self.course} taught by {self.instructor}"

    class Meta:
        # Improve scanning of reviews by course and instructor.
        indexes = [
            models.Index(fields=["course", "instructor"]),
            models.Index(fields=["user", "-created"]),
            models.Index(fields=["instructor", "course"]),
            models.Index(fields=["instructor"]),
            models.Index(fields=["user", "course"]),
        ]


class Vote(models.Model):
    """Vote model.

    Belongs to a User.
    Has a review.
    """

    # Vote value. Required.
    value = models.IntegerField(
        validators=[MinValueValidator(-1), MaxValueValidator(1)]
    )
    # Vote user foreign key. Required.
    user = models.ForeignKey("User", on_delete=models.CASCADE)
    # Vote review foreign key. Required.
    review = models.ForeignKey(Review, on_delete=models.CASCADE)

    def __str__(self):
        """Return human-readable representation of Vote."""
        return f"Vote of value {self.value} for {self.review} by {self.user}"

    class Meta:
        indexes = [
            models.Index(fields=["review"]),
        ]

        constraints = [
            models.UniqueConstraint(
                fields=["user", "review"],
                name="unique vote per user and review",
            )
        ]


class ReviewLLMSummary(models.Model):
    """AI-generated summary of reviews for a course-instructor pair."""

    course = models.ForeignKey("Course", on_delete=models.CASCADE)
    instructor = models.ForeignKey("Instructor", on_delete=models.CASCADE)
    summary_text = models.TextField()
    model_id = models.CharField(max_length=255)
    source_review_count = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        """Return human-readable representation of ReviewLLMSummary."""
        return f"Summary for {self.course} / {self.instructor}"

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["course", "instructor"],
                name="unique_course_instructor_summary",
            )
        ]
