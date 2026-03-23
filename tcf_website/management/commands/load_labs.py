"""
Import lab data from JSON into the database.
This module handles mapping SEAS faculty data to existing departments.
"""

import json
import os

from django.core.management.base import BaseCommand

from tcf_website.models import Department, Lab

# Map keywords found in titles/department fields to DB department names.
# Order matters: more specific matches first.
DEPARTMENT_MAP = {
    "Biomedical Engineering": "Biomedical Engineering",
    "Chemical Engineering": "Chemical Engineering",
    "Civil and Environmental Engineering": "Civil & Environmental Engineering",
    "Civil & Environmental Engineering": "Civil & Environmental Engineering",
    "Computer Science": "Computer Science",
    "Electrical and Computer Engineering": "Electrical & Computer Engineering",
    "Electrical & Computer Engineering": "Electrical & Computer Engineering",
    "Electrical Engineering": "Electrical & Computer Engineering",
    "Engineering and Society": "Science, Technology & Society",
    "Engineering & Society": "Science, Technology & Society",
    "Science, Technology & Society": "Science, Technology & Society",
    "Materials Science and Engineering": "Materials Science & Engineering",
    "Materials Science & Engineering": "Materials Science & Engineering",
    "Mechanical and Aerospace Engineering": "Mechanical & Aerospace Engineering",
    "Mechanical & Aerospace Engineering": "Mechanical & Aerospace Engineering",
    "Systems and Information Engineering": "Systems & Information Engineering",
    "Systems & Information Engineering": "Systems & Information Engineering",
    "Systems Engineering": "Systems & Information Engineering",
    "Applied Mathematics": "Applied Mathematics",
    "Data Science": "Computer Science",
    "General Engineering": "General Engineering",
}


def extract_department(entry):
    """Extract the SEAS department name from a lab entry's titles and department field."""
    all_text = " ".join(entry.get("titles", [])) + " " + (entry.get("department") or "")
    # Try more specific (longer) keys first
    for keyword in sorted(DEPARTMENT_MAP, key=len, reverse=True):
        if keyword.lower() in all_text.lower():
            return DEPARTMENT_MAP[keyword]
    return None


class Command(BaseCommand):
    """Django management command to import lab data from JSON into the database."""

    help = "Imports lab data from labs.json into the database"

    def handle(self, *args, **options):
        """Execute the command to import lab data."""
        json_path = os.path.join(
            os.path.dirname(__file__), "lab_data", "labs.json"
        )

        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Cache department lookups
        dept_cache = {}
        created_count = 0
        updated_count = 0
        skipped = []

        for entry in data:
            dept_name = extract_department(entry)
            if not dept_name:
                skipped.append(entry.get("professorName", "???"))
                continue

            if dept_name not in dept_cache:
                try:
                    dept_cache[dept_name] = Department.objects.get(name=dept_name)
                except Department.DoesNotExist:
                    self.stderr.write(
                        self.style.ERROR(
                            f"Department '{dept_name}' not found in DB. "
                            f"Skipping {entry.get('professorName')}"
                        )
                    )
                    skipped.append(entry.get("professorName", "???"))
                    continue

            department = dept_cache[dept_name]

            # Extract title from titles list
            title = ""
            for t in entry.get("titles", []):
                t_lower = t.lower()
                if any(
                    kw in t_lower
                    for kw in ["professor", "lecturer", "director", "chair", "fellow"]
                ):
                    # Take just the title portion (before the comma/department part)
                    title = t.split(",")[0].strip()
                    break

            # Extract research areas
            research_areas = ", ".join(entry.get("researchInterests", []))

            _, created = Lab.objects.update_or_create(
                pi_name=entry["professorName"],
                defaults={
                    "department": department,
                    "slug": entry.get("slug", ""),
                    "title": title,
                    "description": entry.get("researchDescription", "")
                    or entry.get("descriptionSnippet", ""),
                    "research_areas": research_areas,
                    "website": entry.get("websiteUrl") or "",
                    "email": entry.get("email") or "",
                    "phone": entry.get("phone") or "",
                    "office": entry.get("officeLocation") or "",
                    "photo_url": entry.get("photoUrl") or "",
                    "profile_url": entry.get("profileUrl") or "",
                    "google_scholar": entry.get("googleScholarUrl") or "",
                    "github_url": entry.get("githubUrl") or "",
                    "is_recruiting": entry.get("isRecruiting", False),
                },
            )

            if created:
                created_count += 1
            else:
                updated_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Done: {created_count} created, {updated_count} updated, "
                f"{len(skipped)} skipped"
            )
        )
        if skipped:
            self.stdout.write(
                self.style.WARNING(f"Skipped (no dept match): {', '.join(skipped)}")
            )
