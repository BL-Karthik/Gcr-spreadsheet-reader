
import os
import re
import time
import random

from collections import defaultdict
from datetime import datetime

from dotenv import load_dotenv
from googleapiclient.discovery import build
from gspread.exceptions import APIError


load_dotenv()


def execute_with_retry(operation, max_retries=5):
    """Retry Google API requests when write quota is exceeded."""

    for attempt in range(max_retries):
        try:
            return operation()

        except APIError as exc:
            status_code = getattr(
                getattr(exc, "response", None),
                "status_code",
                None,
            )

            if status_code != 429:
                raise

            if attempt == max_retries - 1:
                raise

            delay = min(2 ** (attempt + 1), 32) + random.uniform(0, 1)

            print(
                "Google API quota exceeded. "
                f"Retrying in {delay:.1f} seconds..."
            )

            time.sleep(delay)


class ReportService:

    def __init__(self, google_sheet_service):
        self.client = google_sheet_service.client
        self.credentials = google_sheet_service.credentials

        self.shared_drive_folder_id = os.getenv(
            "GOOGLE_SHARED_DRIVE_FOLDER_ID"
        )

        self.drive_service = build(
            "drive",
            "v3",
            credentials=self.credentials,
            cache_discovery=False,
        )

    # --------------------------------------------------
    # 1. CHECK WHETHER AN ASSIGNMENT IS SUBMITTED
    # --------------------------------------------------

    @staticmethod
    def is_submitted(status):
        """Return True for statuses counted as submitted."""

        return str(status or "").strip().lower() in {
            "submitted",
            "turned in",
            "returned",
        }

    # --------------------------------------------------
    # 2. SHORTEN COURSE NAME
    # --------------------------------------------------

    @staticmethod
    def get_short_course_name(course_name):
        """
        Example:
        B1P3-603 C1 - SRM Semester 3 - Classroom ...
        becomes:
        B1P3-603C1
        """

        course_name = str(course_name).strip()

        match = re.match(
            r"^(B[12]P\d+-\d+)\s+(C\d+)",
            course_name,
            re.IGNORECASE,
        )

        if match:
            return f"{match.group(1)}{match.group(2)}"

        return course_name

    # --------------------------------------------------
    # 3. COLLECT ASSIGNMENT COLUMNS
    # --------------------------------------------------

    @staticmethod
    def get_assignment_columns(students):
        """Collect unique assignment headers while preserving order."""

        columns = []
        seen = set()

        for student in students:
            statuses = student.get("assignment_statuses", {})

            for column in statuses:
                if column not in seen:
                    seen.add(column)
                    columns.append(column)

        return columns

    # --------------------------------------------------
    # 4. BUILD A STUDENT ROW
    # --------------------------------------------------

    def build_student_row(self, student, assignment_columns):
        """Build one student's row for a course worksheet."""

        statuses = student.get("assignment_statuses", {})

        total = len(assignment_columns)

        submitted = sum(
            1
            for column in assignment_columns
            if self.is_submitted(statuses.get(column, ""))
        )

        percentage = (
            round(submitted / total * 100, 2)
            if total
            else 0.0
        )

        row = [
            student.get("roll_number", ""),
            student.get("student_name", ""),
            f"{submitted}/{total}",
            f"{percentage:g}%",
        ]

        # Preserve the original status of every assignment.
        row.extend(
            statuses.get(column, "")
            for column in assignment_columns
        )

        return row

    # --------------------------------------------------
    # 5. WRITE DATA AND FORMAT A WORKSHEET
    # --------------------------------------------------

    @staticmethod
    def write_rows(worksheet, rows):
        """Write worksheet data and format the header."""

        if not rows:
            return

        col_count = max(len(row) for row in rows)

        # Ensure every row has the same number of columns.
        normalized_rows = [
            row + [""] * (col_count - len(row))
            for row in rows
        ]

        # Write the worksheet data.
        execute_with_retry(
            lambda: worksheet.update(
                range_name="A1",
                values=normalized_rows,
                value_input_option="RAW",
            )
        )

        # Format the header and freeze the first row.
        requests = [
            {
                "repeatCell": {
                    "range": {
                        "sheetId": worksheet.id,
                        "startRowIndex": 0,
                        "endRowIndex": 1,
                        "startColumnIndex": 0,
                        "endColumnIndex": col_count,
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "textFormat": {
                                "bold": True,
                            },
                            "wrapStrategy": "WRAP",
                        },
                    },
                    "fields": (
                        "userEnteredFormat.textFormat.bold,"
                        "userEnteredFormat.wrapStrategy"
                    ),
                },
            },
            {
                "updateSheetProperties": {
                    "properties": {
                        "sheetId": worksheet.id,
                        "gridProperties": {
                            "frozenRowCount": 1,
                            "frozenColumnCount": min(2, col_count),
                        },
                    },
                    "fields": (
                        "gridProperties.frozenRowCount,"
                        "gridProperties.frozenColumnCount"
                    ),
                },
            },
        ]

        execute_with_retry(
            lambda: worksheet.spreadsheet.batch_update(
                {"requests": requests}
            )
        )

    # --------------------------------------------------
    # 6. GENERATE THE REPORT
    # --------------------------------------------------

    def export_course_data_to_sheet(
        self,
        all_course_data,
        start_week,
        end_week,
        batch_name=None,
        share_with_email=None,
        all_course_names=None,
    ):
        """
        Create a report in the configured Shared Drive.

        Creates:
        1. Summary worksheet.
        2. One worksheet for every selected course.

        all_course_names contains all source course tab names.
        Courses with no student records are still included.
        """

        if start_week < 1 or end_week < start_week:
            raise ValueError("Invalid week range.")

        if not self.shared_drive_folder_id:
            raise ValueError(
                "GOOGLE_SHARED_DRIVE_FOLDER_ID is missing from .env."
            )

        all_course_names = all_course_names or []

        # Continue allowing the report when source courses exist
        # but no student records were collected.
        if not all_course_data and not all_course_names:
            raise ValueError(
                "No course or student data available to export."
            )

        batch = (batch_name or "B1_B2").strip().upper()

        title = (
            f"Assignment_Report_{batch}_"
            f"W{start_week}-W{end_week}_"
            f"{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )

        # --------------------------------------------------
        # 6A. CREATE THE SPREADSHEET IN THE SHARED DRIVE
        # --------------------------------------------------

        try:
            created_file = self.drive_service.files().create(
                body={
                    "name": title,
                    "mimeType": (
                        "application/vnd.google-apps.spreadsheet"
                    ),
                    "parents": [self.shared_drive_folder_id],
                },
                supportsAllDrives=True,
                fields="id,name,webViewLink",
            ).execute()

        except Exception as exc:
            raise RuntimeError(
                "Failed to create report in Shared Drive. "
                f"Google API error: {exc}"
            ) from exc

        spreadsheet = self.client.open_by_key(created_file["id"])

        print(f"Created report: {title}")
        print(f"Report spreadsheet ID: {created_file['id']}")

        # --------------------------------------------------
        # 6B. GROUP ALL SOURCE COURSES
        # --------------------------------------------------

        courses = defaultdict(list)

        # Register every selected source course first.
        # This ensures courses without student records are included.
        for course_name in all_course_names:
            course_name = str(course_name).strip()

            if course_name:
                courses[course_name]

        # Add collected student records to their courses.
        for student in all_course_data:
            course_name = (
                str(student.get("course_name", "")).strip()
                or "Unknown Course"
            )

            courses[course_name].append(student)

        print(f"Total courses included: {len(courses)}")
        print(f"Total student-course records: {len(all_course_data)}")

        for course_name, students in sorted(courses.items()):
            print(
                f"Course: {course_name} | "
                f"Students: {len(students)}"
            )

        # --------------------------------------------------
        # 6C. BUILD THE SUMMARY WORKSHEET
        # --------------------------------------------------

        summary = spreadsheet.sheet1

        execute_with_retry(
            lambda: summary.update_title("Summary")
        )

        summary_headers = [
            "# Course Name",
            "# Roll Number",
            "Student Name",
            "Submissions",
            "Percentage",
        ]

        summary_rows = [summary_headers]

        batch_total = 0
        batch_submitted = 0

        for course_name in sorted(courses):
            students = courses[course_name]

            assignment_columns = self.get_assignment_columns(
                students
            )

            short_course_name = self.get_short_course_name(
                course_name
            )

            for student in students:
                student_row = self.build_student_row(
                    student,
                    assignment_columns,
                )

                summary_rows.append(
                    [
                        short_course_name,
                        student_row[0],
                        student_row[1],
                        student_row[2],
                        student_row[3],
                    ]
                )

                statuses = student.get("assignment_statuses", {})

                for column in assignment_columns:
                    batch_total += 1

                    if self.is_submitted(statuses.get(column, "")):
                        batch_submitted += 1

        overall_percentage = (
            round(batch_submitted / batch_total * 100, 2)
            if batch_total
            else 0.0
        )

        summary_rows.append(
            [
                "OVERALL",
                "",
                "",
                f"{batch_submitted}/{batch_total}",
                f"{overall_percentage:g}%",
            ]
        )

        self.write_rows(summary, summary_rows)

        print(
            f"Summary completed: "
            f"{len(all_course_data)} student-course records"
        )

        # --------------------------------------------------
        # 6D. CREATE ONE WORKSHEET PER COURSE
        # --------------------------------------------------

        used_titles = {"summary"}
        course_tab_names = []

        for course_name in sorted(courses):
            students = courses[course_name]

            assignment_columns = self.get_assignment_columns(
                students
            )

            base_title = self.get_short_course_name(course_name)

            # Remove characters prohibited in Google Sheets tab names.
            base_title = re.sub(
                r"[\[\]:*?/\\]",
                "_",
                base_title,
            ).strip("'")

            base_title = base_title[:100] or "Course"

            # Ensure worksheet titles are unique.
            sheet_title = base_title
            suffix = 2

            while sheet_title.casefold() in used_titles:
                suffix_text = f"_{suffix}"

                sheet_title = (
                    base_title[:100 - len(suffix_text)]
                    + suffix_text
                )

                suffix += 1

            used_titles.add(sheet_title.casefold())

            headers = [
                "# Roll Number",
                "Student Name",
                "Submissions",
                "Percentage",
            ] + assignment_columns

            rows = [headers]

            for student in students:
                rows.append(
                    self.build_student_row(
                        student,
                        assignment_columns,
                    )
                )

            # Create the worksheet even when students is empty.
            worksheet = execute_with_retry(
                lambda title=sheet_title, rows_data=rows, cols_count=len(headers):
                    spreadsheet.add_worksheet(
                        title=title,
                        rows=max(len(rows_data), 1),
                        cols=max(cols_count, 1),
                    )
            )

            self.write_rows(worksheet, rows)

            course_tab_names.append(sheet_title)

            print(
                f"Completed {sheet_title}: "
                f"{len(students)} students, "
                f"{len(assignment_columns)} assignments"
            )

            # Reduce the request frequency between course tabs.
            time.sleep(1)

        # --------------------------------------------------
        # 6E. OPTIONALLY SHARE THE REPORT
        # --------------------------------------------------

        if share_with_email:
            execute_with_retry(
                lambda: spreadsheet.share(
                    share_with_email,
                    perm_type="user",
                    role="reader",
                )
            )

            print(f"Report shared with {share_with_email}")

        # --------------------------------------------------
        # 6F. RETURN REPORT DETAILS
        # --------------------------------------------------

        tabs = ["Summary"] + course_tab_names

        print(f"Expected report tabs: {len(tabs)}")
        print(f"Course worksheets created: {len(course_tab_names)}")

        return {
            "report_name": title,
            "report_url": spreadsheet.url,
            "total_students": len(all_course_data),
            "total_courses": len(courses),
            "start_week": start_week,
            "end_week": end_week,
            "batch": batch,
            "tabs": tabs,
            "shared_with": share_with_email,
        }
