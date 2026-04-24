# pylint: disable=missing-class-docstring, fixme, line-too-long, unused-import, no-member
"""TCF schedule models."""

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

from .course import CourseInstructorGrade


class Schedule(models.Model):
    """Schedule Model.

    Belongs to a user and a semester.
    Has a name.

    """

    name = models.CharField(max_length=255)
    user = models.ForeignKey("User", on_delete=models.CASCADE)
    semester = models.ForeignKey("Semester", on_delete=models.CASCADE)
    share_token = models.UUIDField(null=True, blank=True, unique=True, db_index=True)

    def __str__(self):
        return self.name

    class Meta:
        indexes = [
            models.Index(fields=["user", "semester"]),
        ]

    def get_schedule(self):
        """Get the schedule and all its related information"""
        # NOTE: there may be a way to combine all of these methods into
        #       one query, but it would be very complicated

        total_grade_points = 0
        total_course_credits = 0
        courses = self.get_scheduled_courses()

        ret = [
            0
        ] * 5  # intialize return array for the schedule, which will have 5 fields
        ret[0] = courses  # list of courses in the schedule
        # pylint: disable=not-an-iterable
        ret[1] = sum(c.enrolled_units for c in ret[0])
        ret[2] = (
            self.average_rating_for_schedule()
        )  # average rating for the courses in this schedule
        ret[3] = (
            self.average_schedule_difficulty()
        )  # average difficulty for the courses in this schedule

        # calculate weighted gpa based on credits
        for course in courses:
            course_gpa = course.gpa
            course_credits = float(course.enrolled_units)

            if not course_gpa:
                continue  # pass a given course if there is no gpa for it
            total_grade_points += course_gpa * course_credits
            total_course_credits += course_credits

        if total_course_credits:
            ret[4] = total_grade_points / total_course_credits
        else:
            ret[4] = 0.0
        return ret

    def get_scheduled_courses(self):
        """
        Return scheduled courses associated with this schedule,
        including details about the section and instructor.
        """

        queryset = (
            self.scheduledcourse_set.select_related("section", "instructor")
            .annotate(
                avg_recommendability=Coalesce(
                    models.Avg(
                        "section__course__review__recommendability",
                        filter=models.Q(
                            section__course__review__instructor=models.F("instructor")
                        ),
                    ),
                    models.Value(0.0),
                ),
                avg_instructor_rating=Coalesce(
                    models.Avg(
                        "section__course__review__instructor_rating",
                        filter=models.Q(
                            section__course__review__instructor=models.F("instructor")
                        ),
                    ),
                    models.Value(0.0),
                ),
                avg_enjoyability=Coalesce(
                    models.Avg(
                        "section__course__review__enjoyability",
                        filter=models.Q(
                            section__course__review__instructor=models.F("instructor")
                        ),
                    ),
                    models.Value(0.0),
                ),
                difficulty=Coalesce(
                    models.Avg(
                        "section__course__review__difficulty",
                        filter=models.Q(
                            section__course__review__instructor_id=models.F(
                                "instructor"
                            )
                        ),
                    ),
                    models.Value(0.0),
                ),
                title=Concat(
                    models.F("section__course__subdepartment__mnemonic"),
                    models.Value(" "),
                    models.F("section__course__number"),
                    output_field=models.CharField(),
                ),
            )
            .annotate(
                total_rating=models.ExpressionWrapper(
                    (
                        models.F("avg_recommendability")
                        + models.F("avg_instructor_rating")
                        + models.F("avg_enjoyability")
                    )
                    / models.Value(3),
                    output_field=models.FloatField(),
                )
            )
        )

        # Convert queryset to list to allow modifying each instance
        scheduled_courses = list(queryset)

        for scheduled_course in scheduled_courses:
            # Use the average_gpa_for_course method to get the GPA
            gpa = scheduled_course.instructor.average_gpa_for_course(
                scheduled_course.section.course
            )
            # Store the GPA in an attribute of the ScheduledCourse instance
            setattr(scheduled_course, "gpa", gpa)
            setattr(scheduled_course, "credits", scheduled_course.enrolled_units)

        return scheduled_courses

    def calculate_total_rating(self, rating):
        """Calculate the average rating across all categories"""
        total, count = 0, 0
        if rating["avg_recommendability"] is not None:
            total += rating["avg_recommendability"]
            count += 1
        if rating["avg_instructor_rating"] is not None:
            total += rating["avg_instructor_rating"]
            count += 1
        if rating["avg_enjoyability"] is not None:
            total += rating["avg_enjoyability"]
            count += 1
        return total / count if count > 0 else None

    def average_rating_for_schedule(self):
        """Compute average rating for all courses in a schedule.

        Rating is defined as the average of recommendability,
        instructor rating, and enjoyability."""
        # Aggregate average ratings for each instructor-section pair
        aggregated_ratings = (
            ScheduledCourse.objects.filter(schedule=self)
            .annotate(
                related_course_id=models.F("section__course_id"),
                related_instructor_id=models.F("instructor_id"),
                related_section_id=models.F("section_id"),
            )
            .values("related_course_id", "related_instructor_id", "related_section_id")
            .annotate(
                avg_recommendability=models.Avg(
                    "section__course__review__recommendability",
                    filter=models.Q(
                        section__course__review__instructor=models.F(
                            "related_instructor_id"
                        )
                    ),
                ),
                avg_instructor_rating=models.Avg(
                    "section__course__review__instructor_rating",
                    filter=models.Q(
                        section__course__review__instructor=models.F(
                            "related_instructor_id"
                        )
                    ),
                ),
                avg_enjoyability=models.Avg(
                    "section__course__review__enjoyability",
                    filter=models.Q(
                        section__course__review__instructor=models.F(
                            "related_instructor_id"
                        )
                    ),
                ),
            )
        )

        # Compute the overall average across all instructor-section pairs
        total_ratings = 0
        count = 0

        for rating in aggregated_ratings:
            if all(
                key in rating
                for key in [
                    "avg_recommendability",
                    "avg_instructor_rating",
                    "avg_enjoyability",
                ]
            ):
                summed_ratings = self.calculate_total_rating(rating)
                # if summed_ratings is zero, just continue
                # in order to provide better UX, could return some indication that courses
                # were skipped in the calculation
                if not summed_ratings:
                    continue
                total_ratings += summed_ratings
                count += 1  # Since we're summing three ratings for each course

        return total_ratings / count if count > 0 else 0.00

    def average_schedule_difficulty(self):
        """Compute average difficulty score."""

        result = (
            ScheduledCourse.objects.filter(schedule=self)
            .annotate(
                course_id=models.F("section__course_id"),  # Reference to the course
                related_instructor_id=models.F(
                    "instructor_id"
                ),  # Reference to the instructor
            )
            .values("course_id", "related_instructor_id")
            .annotate(
                avg_difficulty=models.Avg(
                    "section__course__review__difficulty",
                    filter=models.Q(
                        section__course__review__instructor_id=models.F(
                            "related_instructor_id"
                        )
                    ),
                )
            )
            .aggregate(overall_avg_difficulty=models.Avg("avg_difficulty"))
        )
        final_result = result.get("overall_avg_difficulty")
        return final_result if final_result else 0.00

    def average_schedule_gpa(self):
        """Compute the average GPA for this schedule"""

        average_gpa = CourseInstructorGrade.objects.filter(
            course__in=ScheduledCourse.objects.values_list(
                "section__course", flat=True
            ),
            instructor__in=ScheduledCourse.objects.values_list("instructor", flat=True),
        ).aggregate(models.Avg("average"))["average__avg"]
        return average_gpa


class ScheduleBookmark(models.Model):
    """Another user's shared schedule saved in the viewer's /schedule sidebar."""

    viewer = models.ForeignKey("User", on_delete=models.CASCADE, related_name="schedule_bookmarks"
    )
    schedule = models.ForeignKey(
        Schedule, on_delete=models.CASCADE, related_name="viewer_bookmarks"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["viewer", "schedule"],
                name="tcf_schedulebookmark_viewer_schedule_uniq",
            )
        ]
        indexes = [
            models.Index(fields=["viewer", "schedule"]),
        ]

    def __str__(self):
        return f"{self.viewer_id} bookmarks {self.schedule_id}"


class ScheduledCourse(models.Model):
    """ScheduledCourse Model.

    Belongs to a schedule and a course section.
    Has a time and instructor.

    """

    # Schedule model foreign key. Required.
    schedule = models.ForeignKey(Schedule, on_delete=models.CASCADE)
    # Section model foreign key. Required.
    section = models.ForeignKey("Section", on_delete=models.CASCADE)
    # Instructor for the section. Required.
    instructor = models.ForeignKey("Instructor", on_delete=models.CASCADE)
    # Time of the section. Required.
    time = models.CharField(max_length=255)
    # Credits the student is taking for this section (always set; equals units_min when fixed).
    enrolled_units = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.section.course} | {self.instructor}"
