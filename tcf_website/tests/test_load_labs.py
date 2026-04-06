"""Tests for the load_labs management helpers."""

from django.test import SimpleTestCase

from tcf_website.management.commands.load_labs import (
    extract_department,
    extract_education,
)


class LoadLabsHelperTests(SimpleTestCase):
    """Unit tests for lab JSON extraction helpers."""

    def test_extract_department_uses_description_fields(self):
        """Department extraction should inspect description text, not just titles."""
        entry = {
            "professorName": "Laura Barnes",
            "titles": ["Professor"],
            "department": "Professor",
            "descriptionSnippet": (
                "Laura Barnes is a professor in the Department of Systems and "
                "Information Engineering."
            ),
            "researchDescription": "",
            "researchInterests": [],
            "labAffiliation": None,
            "officeLocation": None,
            "websiteUrl": None,
        }

        self.assertEqual(
            extract_department(entry), "Systems & Information Engineering"
        )

    def test_extract_department_handles_aliases_and_typos(self):
        """Department extraction should normalize common site variants."""
        entry = {
            "professorName": "Robert S. Salzar",
            "titles": [
                "Associate Professor, Academic General Faculty, Research Track, "
                "Mechancial and Aerospace Engineering"
            ],
            "department": "Mechancial and Aerospace Engineering",
            "descriptionSnippet": "",
            "researchDescription": "",
            "researchInterests": [],
            "labAffiliation": None,
            "officeLocation": None,
            "websiteUrl": None,
        }

        self.assertEqual(
            extract_department(entry), "Mechanical & Aerospace Engineering"
        )

    def test_extract_department_uses_professor_override_when_needed(self):
        """Profiles with only generic titles should still map to a department."""
        entry = {
            "professorName": "Negin Alemazkoor",
            "titles": ["Assistant Professor"],
            "department": "Assistant Professor",
            "descriptionSnippet": (
                "Research focuses on smart and interconnected infrastructure systems."
            ),
            "researchDescription": "",
            "researchInterests": [],
            "labAffiliation": None,
            "officeLocation": "Olsson Hall 102F",
            "websiteUrl": None,
        }

        self.assertEqual(
            extract_department(entry), "Civil & Environmental Engineering"
        )

    def test_extract_education_flattens_raw_values(self):
        """Education entries should be stored in a readable multiline string."""
        entry = {
            "education": [
                {"raw": "B.S. University A"},
                {"raw": "Ph.D. University B"},
                {"label": "Ignored entry"},
            ]
        }

        self.assertEqual(
            extract_education(entry), "B.S. University A\nPh.D. University B"
        )
