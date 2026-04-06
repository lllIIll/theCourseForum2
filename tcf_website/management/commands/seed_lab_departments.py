"""
Seed the minimal School and Department records required by load_labs.
Safe to run multiple times (uses get_or_create).
"""

from django.core.management.base import BaseCommand

from tcf_website.models import Department, School

SEED_DATA = {
    "School of Engineering & Applied Science": [
        "Applied Mathematics",
        "Biomedical Engineering",
        "Chemical Engineering",
        "Civil & Environmental Engineering",
        "Computer Science",
        "Electrical & Computer Engineering",
        "General Engineering",
        "Materials Science & Engineering",
        "Mechanical & Aerospace Engineering",
        "Science, Technology & Society",
        "Systems & Information Engineering",
    ],
    "College of Arts & Sciences": [
        "Environmental Sciences",
    ],
    "School of Medicine": [
        "Medicine",
        "Public Health Sciences",
    ],
}


class Command(BaseCommand):
    help = "Seed schools and departments needed for lab data"

    def handle(self, *args, **options):
        created_schools = 0
        created_depts = 0

        for school_name, dept_names in SEED_DATA.items():
            school, s_created = School.objects.get_or_create(name=school_name)
            if s_created:
                created_schools += 1
                self.stdout.write(f"  Created school: {school_name}")

            for dept_name in dept_names:
                _, d_created = Department.objects.get_or_create(
                    name=dept_name, defaults={"school": school}
                )
                if d_created:
                    created_depts += 1
                    self.stdout.write(f"    Created dept: {dept_name}")

        self.stdout.write(
            self.style.SUCCESS(
                f"Done: {created_schools} schools, {created_depts} departments created."
            )
        )
