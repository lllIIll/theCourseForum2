# pylint: disable=too-few-public-methods
"""Reusable model mixins for tcf_website."""

from django.db import models
from django.db.models.functions import Abs, Coalesce


class Votable(models.Model):
    """Abstract base for objects that accept user upvotes/downvotes.

    Subclasses must expose ``_vote_manager``: the reverse related manager
    pointing at the model's vote table. With that one hook the mixin
    handles toggle semantics (re-voting the same way removes the vote)
    and aggregate counts uniformly across Review, LabReview, Question,
    and Answer.

    The vote tables themselves stay separate per subclass so each can
    keep its own ``unique_together`` constraint and FK target.
    """

    class Meta:
        abstract = True

    @property
    def _vote_manager(self):
        """Return the reverse manager pointing at this object's vote table."""
        raise NotImplementedError(
            "Votable subclasses must define a _vote_manager property "
            "returning the reverse manager for their vote table."
        )

    def count_votes(self):
        """Return {'upvotes': N, 'downvotes': N} aggregated across all votes."""
        return self._vote_manager.aggregate(
            upvotes=Coalesce(models.Sum("value", filter=models.Q(value=1)), 0),
            downvotes=Coalesce(
                Abs(models.Sum("value", filter=models.Q(value=-1))), 0
            ),
        )

    def upvote(self, user):
        """Toggle an upvote from ``user``. Re-upvoting clears the vote."""
        already = self._vote_manager.filter(user=user, value=1).exists()
        self._vote_manager.filter(user=user).delete()
        if not already:
            self._vote_manager.create(user=user, value=1)

    def downvote(self, user):
        """Toggle a downvote from ``user``. Re-downvoting clears the vote."""
        already = self._vote_manager.filter(user=user, value=-1).exists()
        self._vote_manager.filter(user=user).delete()
        if not already:
            self._vote_manager.create(user=user, value=-1)
