"""
Import lab reviews from Supabase into the local database.
"""

import os

import requests
from django.core.management.base import BaseCommand

from tcf_website.models import Lab, LabReview


def fetch_reviews_from_supabase():
    """Fetch all approved lab reviews from Supabase REST API."""
    url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    key = os.environ.get("SUPABASE_ANON_KEY", "")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_ANON_KEY must be set in .env")

    headers = {"apikey": key, "Authorization": f"Bearer {key}"}
    all_rows = []
    page_size = 1000
    offset = 0

    while True:
        resp = requests.get(
            f"{url}/rest/v1/reviews",
            headers={**headers, "Range": f"{offset}-{offset + page_size - 1}"},
            params={
                "select": "*,labs(slug)",
                "is_approved": "eq.true",
                "order": "created_at.asc",
            },
            timeout=30,
        )
        resp.raise_for_status()
        rows = resp.json()
        all_rows.extend(rows)
        if len(rows) < page_size:
            break
        offset += page_size

    return all_rows


def map_role(supabase_role):
    """Map Supabase role string to Django ROLE_CHOICES key."""
    role_map = {
        "undergrad_ra": "undergrad_ra",
        "undergraduate_ra": "undergrad_ra",
        "grad_ra": "grad_ra",
        "graduate_ra": "grad_ra",
        "postdoc": "postdoc",
        "staff": "staff",
    }
    return role_map.get((supabase_role or "").lower(), "other")


class Command(BaseCommand):
    help = "Import lab reviews from Supabase into the local database."

    def handle(self, *args, **options):
        self.stdout.write("Fetching reviews from Supabase...")
        try:
            rows = fetch_reviews_from_supabase()
        except RuntimeError as e:
            self.stderr.write(str(e))
            return

        self.stdout.write(f"Found {len(rows)} approved reviews.")

        # Build slug → Lab map for fast lookup
        lab_by_slug = {lab.slug: lab for lab in Lab.objects.only("id", "slug")}

        created_count = 0
        updated_count = 0
        skipped_count = 0

        for row in rows:
            # Get slug from embedded labs relation
            lab_data = row.get("labs") or {}
            slug = lab_data.get("slug") if isinstance(lab_data, dict) else None
            if not slug:
                self.stdout.write(
                    self.style.WARNING(f"  Skipping review {row.get('id')}: no slug")
                )
                skipped_count += 1
                continue

            lab = lab_by_slug.get(slug)
            if not lab:
                self.stdout.write(
                    self.style.WARNING(
                        f"  Skipping review {row.get('id')}: lab '{slug}' not in Django DB"
                    )
                )
                skipped_count += 1
                continue

            # Build period string from start/end
            period_start = row.get("period_start") or ""
            period_end = row.get("period_end") or ""
            if period_start and period_end:
                period = f"{period_start} - {period_end}"
            else:
                period = period_start or period_end or ""

            defaults = {
                "overall": row.get("rating_overall") or 3,
                "mentorship": row.get("rating_mentorship") or 3,
                "work_life": row.get("rating_work_life") or 3,
                "friendliness": row.get("rating_friendliness") or 3,
                "inclusivity": row.get("rating_inclusivity") or 3,
                "responsiveness": row.get("rating_responsiveness") or 3,
                "hours_per_week": min(max(row.get("hours_per_week") or 0, 0), 80),
                "would_recommend": row.get("would_recommend") or False,
                "text": row.get("review_text") or "",
                "role": map_role(row.get("role")),
                "period": period,
                "how_joined": row.get("how_they_joined") or "",
                "advice": row.get("advice_for_newcomers") or "",
                "hidden": False,
                "lab": lab,
            }

            # Supabase reviews have no Django user — use a sentinel system user.
            # LabReview requires a user FK so we fetch/create a placeholder.
            from django.contrib.auth import get_user_model
            User = get_user_model()
            system_user, _ = User.objects.get_or_create(
                username="supabase_import",
                defaults={"is_active": False, "email": ""},
            )
            defaults["user"] = system_user

            supabase_uuid = row.get("id")
            if not supabase_uuid:
                skipped_count += 1
                continue

            _, created = LabReview.objects.update_or_create(
                supabase_id=supabase_uuid,
                defaults=defaults,
            )
            if created:
                created_count += 1
            else:
                updated_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. Created: {created_count}, Updated: {updated_count}, "
                f"Skipped: {skipped_count}"
            )
        )
