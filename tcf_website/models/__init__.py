# pylint: disable=line-too-long

"""TCF Models package.

Splits the historical models.py monolith into domain-scoped submodules.
See https://docs.djangoproject.com/en/3.0/topics/db/models/#organizing-models-in-a-package
"""

from .user import User
from .club import ClubCategory, Club
from .course import School, Department, Subdepartment, Instructor, Semester, Discipline, Course, CourseGrade, CourseInstructorGrade, Section, SectionTime
from .schedule import Schedule, ScheduleBookmark, ScheduledCourse
from .review import Review, Vote, ReviewLLMSummary
from .lab import Lab, LabReview, LabVote
from .question import Answer, Question  # VoteQuestion / VoteAnswer intentionally not re-exported here, matching the pre-split admin surface
