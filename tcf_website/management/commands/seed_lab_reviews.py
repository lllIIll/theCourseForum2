"""
Seed sample lab reviews for development/preview purposes.

Creates placeholder reviews with mid-range ratings so the metrics UI
is visible without needing real Supabase review data. Safe to run
multiple times (idempotent via get_or_create on the seed user).

Usage:
    python manage.py seed_lab_reviews          # seeds first 10 labs
    python manage.py seed_lab_reviews --all    # seeds all labs
    python manage.py seed_lab_reviews --clear  # removes all seed reviews
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from tcf_website.models import Lab, LabReview

SEED_USERNAME = "seed_data"

SAMPLE_REVIEWS = [
    {
        "overall": 4,
        "mentorship": 4,
        "work_life": 4,
        "friendliness": 4,
        "inclusivity": 4,
        "responsiveness": 4,
        "hours_per_week": 20,
        "role": "undergrad_ra",
        "period": "Fall 2024 - Spring 2025",
        "would_recommend": True,
        "text": "Great experience overall. The PI was very supportive and the lab culture was welcoming.",
        "how_joined": "Cold email",
        "advice": "Reach out early and show genuine interest in their research.",
    },
    {
        "overall": 4,
        "mentorship": 5,
        "work_life": 3,
        "friendliness": 4,
        "inclusivity": 4,
        "responsiveness": 4,
        "hours_per_week": 25,
        "role": "undergrad_ra",
        "period": "Spring 2025",
        "would_recommend": True,
        "text": "Really learned a lot. Hours can be demanding but the mentorship makes it worth it.",
        "how_joined": "Professor's class",
        "advice": "Come in with specific questions about their current projects.",
    },
]


class Command(BaseCommand):
    help = "Seed sample lab reviews for development UI preview."

    def add_arguments(self, parser):
        parser.add_argument(
            "--all",
            action="store_true",
            help="Seed all labs (default: first 10)",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Remove all seed reviews instead of creating them",
        )

    def handle(self, *args, **options):
        User = get_user_model()

        if options["clear"]:
            deleted, _ = LabReview.objects.filter(
                user__username=SEED_USERNAME
            ).delete()
            self.stdout.write(self.style.SUCCESS(f"Removed {deleted} seed reviews."))
            return

        # Get or create the seed system user
        seed_user, created = User.objects.get_or_create(
            username=SEED_USERNAME,
            defaults={"is_active": False, "email": ""},
        )
        if created:
            self.stdout.write(f"Created seed user '{SEED_USERNAME}'.")

        labs = Lab.objects.all()
        if not options["all"]:
            labs = labs[:10]

        created_count = 0
        for lab in labs:
            # Skip if this lab already has seed reviews
            if LabReview.objects.filter(lab=lab, user=seed_user).exists():
                continue

            for review_data in SAMPLE_REVIEWS:
                LabReview.objects.create(
                    lab=lab,
                    user=seed_user,
                    **review_data,
                )
                created_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Created {created_count} seed reviews across "
                f"{labs.count() if not options['all'] else 'all'} labs."
            )
        )
        self.stdout.write(
            "Run with --clear to remove seed data before going to production."
        )
