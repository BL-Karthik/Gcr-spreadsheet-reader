
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
                None
            )

            if status_code != 429:
                raise

            if attempt == max_retries - 1:
                raise

            delay = min(2 ** (attempt + 1), 32) + random.uniform(0, 1)

            print(
                f"Google API quota exceeded. "
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
            cache_discovery=False
        )

    @staticmethod
    def is_submitted(status):
        """
        Count these statuses as submitted.
        Change this set if your reporting rules differ.
        """
        return str(status or "").strip().lower() in {
            "submitted",
            "turned in",
            "returned"
        }

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
            re.IGNORECASE
        )

        if match:
            return f"{match.group(1)}{match.group(2)}"

        return course_name

    @staticmethod
    def get_assignment_columns(students):
        """
        Collect unique assignment headers while preserving
        the order in which they appear in the source data.
        """
        columns = []
        seen = set()

        for student in students:
            statuses = student.get("assignment_statuses", {})

            for column in statuses:
                if column not in seen:
                    seen.add(column)
                    columns.append(column)

        return columns

    def build_student_row(self, student, assignment_columns):
        """Build a student's row for a course worksheet."""
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
            f"{percentage:g}%"
        ]

        # Preserve each original assignment status.
        row.extend(
            statuses.get(column, "")
            for column in assignment_columns
        )

        return row

    @staticmethod
    def write_rows(worksheet, rows):
        """
        Write worksheet data, then combine header formatting
        and freeze-pane settings into one batch request.
        """
        if not rows:
            return

        col_count = len(rows[0])

        # One request to write the data.
        execute_with_retry(
            lambda: worksheet.update(
                range_name="A1",
                values=rows,
                value_input_option="RAW"
            )
        )

        # One batch request for formatting and freezing.
        requests = [
            {
                "repeatCell": {
                    "range": {
                        "sheetId": worksheet.id,
                        "startRowIndex": 0,
                        "endRowIndex": 1,
                        "startColumnIndex": 0,
                        "endColumnIndex": col_count
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "textFormat": {
                                "bold": True
                            },
                            "wrapStrategy": "WRAP"
                        }
                    },
                    "fields": (
                        "userEnteredFormat.textFormat.bold,"
                        "userEnteredFormat.wrapStrategy"
                    )
                }
            },
            {
                "updateSheetProperties": {
                    "properties": {
                        "sheetId": worksheet.id,
                        "gridProperties": {
                            "frozenRowCount": 1,
                            "frozenColumnCount": min(2, col_count)
                        }
                    },
                    "fields": (
                        "gridProperties.frozenRowCount,"
                        "gridProperties.frozenColumnCount"
                    )
                }
            }
        ]

        execute_with_retry(
            lambda: worksheet.spreadsheet.batch_update(
                {"requests": requests}
            )
        )

    def export_course_data_to_sheet(
        self,
        all_course_data,
        start_week,
        end_week,
        batch_name=None,
        share_with_email=None
    ):
        """
        Create a report in the configured Shared Drive.

        Sheets created:
        1. Summary: one row per student and an overall row.
        2. One worksheet per course with individual assignment statuses.
        """

        if not all_course_data:
            raise ValueError(
                "No student data available to export."
            )

        if start_week < 1 or end_week < start_week:
            raise ValueError("Invalid week range.")

        if not self.shared_drive_folder_id:
            raise ValueError(
                "GOOGLE_SHARED_DRIVE_FOLDER_ID is missing from .env."
            )

        batch = (batch_name or "B1_B2").strip().upper()

        title = (
            f"Assignment_Report_{batch}_"
            f"W{start_week}-W{end_week}_"
            f"{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )

        # --------------------------------------------------
        # 1. Create spreadsheet in the Shared Drive
        # --------------------------------------------------
        try:
            created_file = self.drive_service.files().create(
                body={
                    "name": title,
                    "mimeType": (
                        "application/vnd.google-apps.spreadsheet"
                    ),
                    "parents": [self.shared_drive_folder_id]
                },
                supportsAllDrives=True,
                fields="id,name,webViewLink"
            ).execute()

        except Exception as exc:
            raise RuntimeError(
                "Failed to create report in Shared Drive. "
                f"Google API error: {exc}"
            ) from exc

        spreadsheet = self.client.open_by_key(
            created_file["id"]
        )

        # --------------------------------------------------
        # 2. Group records by course
        # --------------------------------------------------
        courses = defaultdict(list)

        for student in all_course_data:
            course_name = (
                str(student.get("course_name", "")).strip()
                or "Unknown Course"
            )

            courses[course_name].append(student)

        # --------------------------------------------------
        # 3. Build the Summary worksheet
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
            "Percentage"
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
                    assignment_columns
                )

                summary_rows.append([
                    short_course_name,
                    student_row[0],
                    student_row[1],
                    student_row[2],
                    student_row[3]
                ])

                statuses = student.get(
                    "assignment_statuses", {}
                )

                for column in assignment_columns:
                    batch_total += 1

                    if self.is_submitted(
                        statuses.get(column, "")
                    ):
                        batch_submitted += 1

        overall_percentage = (
            round(batch_submitted / batch_total * 100, 2)
            if batch_total
            else 0.0
        )

        summary_rows.append([
            "OVERALL",
            "",
            "",
            f"{batch_submitted}/{batch_total}",
            f"{overall_percentage:g}%"
        ])

        self.write_rows(summary, summary_rows)

        print(
            f"Summary completed: "
            f"{len(all_course_data)} student-course records"
        )

        # Small pause before creating and writing course tabs.
        time.sleep(1)

        # --------------------------------------------------
        # 4. Create one worksheet for each course
        # --------------------------------------------------
        used_titles = {"summary"}
        course_tab_names = []

        for course_name in sorted(courses):
            students = courses[course_name]

            assignment_columns = self.get_assignment_columns(
                students
            )

            base_title = self.get_short_course_name(course_name)

            # Remove characters prohibited in worksheet names.
            base_title = re.sub(
                r"[\[\]:*?/\\]",
                "_",
                base_title
            ).strip("'")

            base_title = base_title[:100] or "Course"

            # Ensure unique worksheet names.
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
            course_tab_names.append(sheet_title)

            headers = [
                "# Roll Number",
                "Student Name",
                "Submissions",
                "Percentage"
            ] + assignment_columns

            rows = [headers]

            for student in students:
                rows.append(
                    self.build_student_row(
                        student,
                        assignment_columns
                    )
                )

            # Creating the worksheet is a separate API request.
            worksheet = execute_with_retry(
                lambda: spreadsheet.add_worksheet(
                    title=sheet_title,
                    rows=max(len(rows), 1),
                    cols=max(len(headers), 1)
                )
            )

            self.write_rows(worksheet, rows)

            print(
                f"Completed {sheet_title}: "
                f"{len(students)} students, "
                f"{len(assignment_columns)} assignments"
            )

            # Reduce request frequency between course tabs.
            time.sleep(1)

        # --------------------------------------------------
        # 5. Optionally share the report
        # --------------------------------------------------
        if share_with_email:
            execute_with_retry(
                lambda: spreadsheet.share(
                    share_with_email,
                    perm_type="user",
                    role="reader"
                )
            )

            print(
                f"Report shared with {share_with_email}"
            )

        # --------------------------------------------------
        # 6. Return report details to the API router
        # --------------------------------------------------
        return {
            "report_name": title,
            "report_url": spreadsheet.url,
            "total_students": len(all_course_data),
            "total_courses": len(courses),
            "start_week": start_week,
            "end_week": end_week,
            "batch": batch,
            "tabs": ["Summary"] + course_tab_names,
            "shared_with": share_with_email
        }
