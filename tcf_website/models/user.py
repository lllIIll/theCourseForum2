# pylint: disable=missing-class-docstring, fixme, line-too-long, unused-import, no-member
"""TCF user models."""

from django.contrib.auth.models import AbstractUser
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class User(AbstractUser):
    """User model.

    Has many Reviews.
    """

    # User computing ID. Not required by database schema, but is
    # necessary. Should be created during authentication pipeline.
    computing_id = models.CharField(max_length=20, unique=True, blank=True)
    # User graduation year. Not required by database schema, but is
    # necessary. Should be created during authentication pipeline.
    graduation_year = models.IntegerField(
        validators=[MinValueValidator(2000), MaxValueValidator(2999)],
        blank=True,
        null=True,
    )

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.email})"

    def full_name(self):
        """Return string containing user full name."""
        return f"{self.first_name} {self.last_name}"

    def reviews(self):
        """Return user reviews sorted by creation date."""
        return self.review_set.annotate(
            sum_votes=models.functions.Coalesce(
                models.Sum("vote__value"), models.Value(0)
            ),
            user_vote=models.functions.Coalesce(
                models.Sum("vote__value", filter=models.Q(vote__user=self)),
                models.Value(0),
            ),
        ).order_by("-created")

    def schedules(self):
        """Return user schedules"""
        return self.schedule_set.all()
