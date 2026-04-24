"""
Import lab data from Supabase into the local database.
"""

import os

import requests
from django.core.management.base import BaseCommand

from tcf_website.models import Department, Lab

DEPARTMENT_MAP = {
    "Biomedical Engineering": "Biomedical Engineering",
    "Chemical Engineering": "Chemical Engineering",
    "Chemical Process": "Chemical Engineering",
    "Civil and Environmental Engineering": "Civil & Environmental Engineering",
    "Civil & Environmental Engineering": "Civil & Environmental Engineering",
    "Civil Engineering": "Civil & Environmental Engineering",
    "Computer Science": "Computer Science",
    "Computer Engineering": "Electrical & Computer Engineering",
    "Electrical and Computer Engineering": "Electrical & Computer Engineering",
    "Electrical & Computer Engineering": "Electrical & Computer Engineering",
    "Electrical Engineering": "Electrical & Computer Engineering",
    "Engineering and Society": "Science, Technology & Society",
    "Engineering & Society": "Science, Technology & Society",
    "Science, Technology & Society": "Science, Technology & Society",
    "Science, Technology, and Society": "Science, Technology & Society",
    "Materials Science and Engineering": "Materials Science & Engineering",
    "Materials Science & Engineering": "Materials Science & Engineering",
    "Mechanical and Aerospace Engineering": "Mechanical & Aerospace Engineering",
    "Mechanical & Aerospace Engineering": "Mechanical & Aerospace Engineering",
    "Mechanical and Aeropsace Engineering": "Mechanical & Aerospace Engineering",
    "Mechancial and Aerospace Engineering": "Mechanical & Aerospace Engineering",
    "Systems and Information Engineering": "Systems & Information Engineering",
    "Systems & Information Engineering": "Systems & Information Engineering",
    "Systems Engineering": "Systems & Information Engineering",
    "Applied Mathematics": "Applied Mathematics",
    "Data Science": "Computer Science",
    "General Engineering": "General Engineering",
    "School of Engineering and Applied Science": "General Engineering",
    "School of Engineering & Applied Science": "General Engineering",
    "First Year Engineering Center": "General Engineering",
    "First Year Engineering": "General Engineering",
    "Engineering Education": "General Engineering",
    "Engineering Science": "General Engineering",
    "Environmental Science": "Environmental Sciences",
    "School of Medicine": "Medicine",
    "Cardiovascular Medicine": "Medicine",
    "Ophthalmology": "Medicine",
    "Public Health Sciences": "Public Health Sciences",
    "Biostatistics": "Public Health Sciences",
    "Molecular Immunology": "Biomedical Engineering",
    "Signal and Image Processing": "Electrical & Computer Engineering",
}

PROFESSOR_DEPARTMENT_OVERRIDES = {
    "Negin Alemazkoor": "Civil & Environmental Engineering",
    "Eric Anderson": "Chemical Engineering",
    "Brian H. Annex": "Medicine",
    "James Cheng": "General Engineering",
    "Joshua Darville, Ph.D.": "Systems & Information Engineering",
    "William Davis": "Science, Technology & Society",
    "Keivan Esfarjani": "Materials Science & Engineering",
    "Jim Fitz-Gerald": "Materials Science & Engineering",
    "Richard D. Jacques": "General Engineering",
    "Alexander L (Sasha) Klibanov": "Biomedical Engineering",
    "Leidy Klotz": "Civil & Environmental Engineering",
    "Zhen (Leo) Liu": "Civil & Environmental Engineering",
    "Ji Ma": "Materials Science & Engineering",
    "Stephen J. McDonnell": "Materials Science & Engineering",
    "Julianne Quinn": "Civil & Environmental Engineering",
    "Adarsh Ramakrishnan": "General Engineering",
    "Karina Ripley": "Science, Technology & Society",
    "Bryn Elizabeth Seabrook": "Science, Technology & Society",
    "Giovanni Zangari": "Materials Science & Engineering",
}


def extract_department(lab):
    """Return the best matching Django department name for a Supabase lab row."""
    search_text = " ".join(filter(None, [
        lab.get("department", ""),
        " ".join(lab.get("titles") or []),
        lab.get("research_area", ""),
        lab.get("lab_affiliation", ""),
        lab.get("research_description", ""),
        " ".join(lab.get("research_areas") or []),
        " ".join(lab.get("research_interests") or []),
    ]))

    for keyword in sorted(DEPARTMENT_MAP, key=len, reverse=True):
        if keyword.lower() in search_text.lower():
            return DEPARTMENT_MAP[keyword]

    return PROFESSOR_DEPARTMENT_OVERRIDES.get(lab.get("professor_name"))


def extract_education(lab):
    """Flatten Supabase education JSONB into a readable multiline string."""
    education = lab.get("education") or []
    if isinstance(education, list):
        return "\n".join(
            item.get("raw", "").strip()
            for item in education
            if isinstance(item, dict) and item.get("raw")
        )
    return ""


def fetch_labs_from_supabase():
    """Fetch all lab rows from Supabase REST API."""
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
            f"{url}/rest/v1/labs",
            headers={**headers, "Range": f"{offset}-{offset + page_size - 1}"},
            params={"select": "*", "order": "professor_name.asc"},
            timeout=30,
        )
        resp.raise_for_status()
        rows = resp.json()
        all_rows.extend(rows)
        if len(rows) < page_size:
            break
        offset += page_size

    return all_rows


class Command(BaseCommand):
    help = "Import lab data from Supabase into the local database"

    def handle(self, *args, **options):
        """Entry point for the management command."""
        self.stdout.write("Fetching labs from Supabase...")
        labs = fetch_labs_from_supabase()
        self.stdout.write(f"Fetched {len(labs)} labs.")

        dept_cache = {}
        created_count = 0
        updated_count = 0
        skipped = []

        for lab in labs:
            dept_name = extract_department(lab)
            if not dept_name:
                skipped.append(lab.get("professor_name", "???"))
                continue

            if dept_name not in dept_cache:
                try:
                    dept_cache[dept_name] = Department.objects.get(name=dept_name)
                except Department.DoesNotExist:
                    self.stderr.write(
                        self.style.ERROR(
                            f"Department '{dept_name}' not found in DB. "
                            f"Skipping {lab.get('professor_name')}"
                        )
                    )
                    skipped.append(lab.get("professor_name", "???"))
                    continue

            department = dept_cache[dept_name]

            research_areas = ", ".join(filter(None, [
                ", ".join(lab.get("research_areas") or []),
                ", ".join(lab.get("research_interests") or []),
                lab.get("research_area") or "",
            ]))

            _, created = Lab.objects.update_or_create(
                pi_name=lab["professor_name"],
                defaults={
                    "department": department,
                    "slug": lab.get("slug") or "",
                    "title": (lab.get("titles") or [""])[0].split(",")[0].strip(),
                    "description": lab.get("research_description") or lab.get("description") or "",
                    "research_areas": research_areas,
                    "website": lab.get("website_url") or "",
                    "email": lab.get("email") or "",
                    "phone": lab.get("phone") or "",
                    "office": lab.get("office_location") or "",
                    "photo_url": lab.get("profile_image_url") or "",
                    "profile_url": lab.get("seas_profile_url") or "",
                    "google_scholar": lab.get("google_scholar_url") or "",
                    "github_url": lab.get("github_url") or "",
                    "education": extract_education(lab),
                    "is_recruiting": lab.get("is_recruiting") or False,
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
