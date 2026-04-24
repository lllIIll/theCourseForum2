# pylint: disable=missing-class-docstring, fixme, line-too-long, unused-import, no-member
"""TCF lab models."""

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

from .course import Department
from .mixins import Votable
from .user import User


class Lab(models.Model):
    """Lab model.

    Belongs to a Department.
    Has many LabReviews.
    """

    # PI full name. Required.
    pi_name = models.CharField(max_length=255)
    # URL slug, auto-generated from pi_name. Required.
    slug = models.SlugField(max_length=255, unique=True)
    # Department foreign key. Required.
    department = models.ForeignKey("Department", on_delete=models.CASCADE)
    # PI title, e.g. "Professor", "Associate Professor". Optional.
    title = models.CharField(max_length=255, blank=True)
    # Research description/bio. Optional.
    description = models.TextField(blank=True)
    # Comma-separated research interests. Optional.
    research_areas = models.TextField(blank=True)
    # Lab website URL. Optional.
    website = models.URLField(blank=True)
    # PI email. Optional.
    email = models.EmailField(blank=True)
    # PI phone number. Optional.
    phone = models.CharField(max_length=50, blank=True)
    # Office location. Optional.
    office = models.CharField(max_length=255, blank=True)
    # Photo URL. Optional.
    photo_url = models.CharField(max_length=512, blank=True)
    # Faculty profile URL. Optional.
    profile_url = models.URLField(blank=True)
    # Google Scholar URL. Optional.
    google_scholar = models.URLField(blank=True)
    # GitHub URL. Optional.
    github_url = models.URLField(blank=True)
    # Education background. Optional.
    education = models.TextField(blank=True)
    # Whether the lab is actively recruiting. Required.
    is_recruiting = models.BooleanField(default=False)
    # Combined text for trigram search. Auto-populated.
    combined_search_text = models.CharField(max_length=1024, blank=True, editable=False)

    def save(self, *args, **kwargs):
        """Auto-generate slug from pi_name and compute combined_search_text."""
        if not self.slug:
            from django.utils.text import slugify

            base_slug = slugify(self.pi_name)
            slug = base_slug
            counter = 2
            while Lab.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        parts = [self.pi_name, self.research_areas, self.department.name]
        self.combined_search_text = " ".join(p for p in parts if p)[:1024]
        super().save(*args, **kwargs)

    def avg_ratings(self):
        """Compute average ratings across all lab reviews."""
        return self.labreview_set.aggregate(
            overall=Avg("overall"),
            mentorship=Avg("mentorship"),
            lab_culture=Avg("lab_culture"),
            responsiveness=Avg("responsiveness"),
            independence=Avg("independence"),
            entry_selectivity=Avg("entry_selectivity"),
            hours_per_week=Avg("hours_per_week"),
        )

    def __str__(self):
        """String representation of Lab."""
        return self.pi_name

    class Meta:
        indexes = [
            GinIndex(
                fields=["combined_search_text"],
                opclasses=["gin_trgm_ops"],
                name="lab_combined_search_text",
            ),
        ]


class LabReview(Votable):
    """Lab review model.

    Belongs to a User and a Lab.
    """

    RATINGS = (
        (1, 1),
        (2, 2),
        (3, 3),
        (4, 4),
        (5, 5),
    )

    ROLE_CHOICES = (
        ("undergrad_ra", "Undergraduate RA"),
        ("grad_ra", "Graduate RA"),
        ("postdoc", "Postdoc"),
        ("staff", "Staff"),
        ("other", "Other"),
    )

    # Lab foreign key. Required.
    lab = models.ForeignKey(Lab, on_delete=models.CASCADE)
    # User foreign key. Required.
    user = models.ForeignKey("User", on_delete=models.CASCADE)

    # Lab rating dimensions (1-5). All required.
    overall = models.PositiveSmallIntegerField(choices=RATINGS)
    mentorship = models.PositiveSmallIntegerField(choices=RATINGS)
    lab_culture = models.PositiveSmallIntegerField(choices=RATINGS)
    responsiveness = models.PositiveSmallIntegerField(choices=RATINGS)
    independence = models.PositiveSmallIntegerField(choices=RATINGS)
    entry_selectivity = models.PositiveSmallIntegerField(choices=RATINGS)

    # Hours per week spent in lab. Required.
    hours_per_week = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(80)]
    )
    # Reviewer's role in the lab. Required.
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    # Time period of lab experience, e.g. "Fall 2024 - Spring 2025". Required.
    period = models.CharField(max_length=100)
    # How the reviewer joined the lab. Optional.
    how_joined = models.TextField(blank=True)
    # Advice for future students. Optional.
    advice = models.TextField(blank=True)
    # Whether the reviewer would recommend the lab. Required.
    would_recommend = models.BooleanField(default=True)
    # Review text. Optional.
    text = models.TextField(blank=True)

    # Review visibility. Required. Default visible.
    hidden = models.BooleanField(default=False)
    # Toxicity rating of review.
    toxicity_rating = models.IntegerField(default=0)
    # Most relevant toxicity category, only exists if review has text.
    toxicity_category = models.CharField(blank=True)
    # Supabase UUID for idempotent syncing. Optional.
    supabase_id = models.UUIDField(null=True, blank=True, unique=True, db_index=True)
    # Review created date. Required.
    created = models.DateTimeField(auto_now_add=True)
    # Review modified date. Required.
    modified = models.DateTimeField(auto_now=True)

    @property
    def _vote_manager(self):
        """Return the reverse manager pointing at this object's vote table."""
        return self.labvote_set

    @staticmethod
    def sort(reviews, method=""):
        """Sort reviews by given method."""
        match method:
            case "Most Helpful":
                return reviews.annotate(
                    upvotes=Coalesce(Sum("labvote__value", filter=Q(labvote__value=1)), 0),
                    downvotes=Coalesce(
                        Abs(Sum("labvote__value", filter=Q(labvote__value=-1))), 0
                    ),
                    helpful_score=ExpressionWrapper(
                        F("upvotes") - F("downvotes"),
                        output_field=fields.IntegerField(),
                    ),
                ).order_by("-helpful_score")
            case "Highest Rating":
                return reviews.order_by("-overall")
            case "Lowest Rating":
                return reviews.order_by("overall")
            case "Most Recent":
                return reviews.order_by("-created")
            case "Default" | _:
                return reviews

    @staticmethod
    def paginate(reviews, page_number, per_page=10):
        """Paginate reviews."""
        paginator = Paginator(reviews, per_page)
        try:
            return paginator.page(page_number)
        except PageNotAnInteger:
            return paginator.page(1)
        except EmptyPage:
            return paginator.page(paginator.num_pages)

    def __str__(self):
        """String representation of LabReview."""
        return f"Lab review by {self.user} for {self.lab}"

    class Meta:
        indexes = [
            models.Index(fields=["lab"]),
            models.Index(fields=["user", "-created"]),
        ]


class LabVote(models.Model):
    """LabVote model.

    Belongs to a User.
    Has a LabReview.
    """

    # Vote value. Required.
    value = models.IntegerField(
        validators=[MinValueValidator(-1), MaxValueValidator(1)]
    )
    # Vote user foreign key. Required.
    user = models.ForeignKey("User", on_delete=models.CASCADE)
    # Vote lab review foreign key. Required.
    review = models.ForeignKey(LabReview, on_delete=models.CASCADE)

    def __str__(self):
        """String representation of LabVote."""
        return f"LabVote of value {self.value} for {self.review} by {self.user}"

    class Meta:
        indexes = [
            models.Index(fields=["review"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "review"],
                name="unique lab vote per user and review",
            )
        ]
