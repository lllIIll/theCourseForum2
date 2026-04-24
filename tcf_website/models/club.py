# pylint: disable=missing-class-docstring, fixme, line-too-long, unused-import, no-member
"""TCF club models."""

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


class ClubCategory(models.Model):
    """ClubCategory model.

    Has many Clubs.
    """

    # Human name
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True)
    # slug for routing in the existing course URL
    slug = models.SlugField(max_length=255, unique=True)

    def __str__(self):
        return self.name


class Club(models.Model):
    """Club model.

    Belongs to a ClubCategory.
    Has many Reviews.
    """

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    category = models.ForeignKey(ClubCategory, on_delete=models.CASCADE)
    combined_name = models.CharField(max_length=255, blank=True, editable=False)
    application_required = models.BooleanField(default=False)
    photo_url = models.CharField(max_length=255, blank=True)
    meeting_time = models.CharField(max_length=255, blank=True)

    def save(self, *args, **kwargs):
        # maintain combined_name for trigram search
        self.combined_name = self.name
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    class Meta:
        indexes = [
            GinIndex(
                fields=["combined_name"],
                opclasses=["gin_trgm_ops"],
                name="club_combined_name",
            ),
        ]
