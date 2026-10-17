
import re
import os

from dotenv import load_dotenv
import gspread
from google.oauth2.service_account import Credentials


load_dotenv()


class GoogleSheetService:

    SCOPES = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive.file",
    ]

    B1_SPREADSHEET_ID = os.getenv("B1_SPREADSHEET_ID")
    B2_SPREADSHEET_ID = os.getenv("B2_SPREADSHEET_ID")

    def __init__(self):
        """Initialize the authenticated Google Sheets client."""

        self.credentials = Credentials.from_service_account_file(
            "credentials/service_account.json",
            scopes=self.SCOPES,
        )

        self.client = gspread.authorize(self.credentials)

    # --------------------------------------------------
    # 1. GET ALL COURSE TITLES
    # --------------------------------------------------

    def getAllcoursesTitles(self):
        """Return the course names from B1 and B2."""

        course_names = []

        for spreadsheet_id in (
            self.B1_SPREADSHEET_ID,
            self.B2_SPREADSHEET_ID,
        ):
            if not spreadsheet_id:
                continue

            spreadsheet = self.client.open_by_key(spreadsheet_id)

            for worksheet in spreadsheet.worksheets():
                match = re.match(
                    r"^(B[12]P\d+-\d+\s+C\d+)\s+-",
                    worksheet.title,
                    re.IGNORECASE,
                )

                if match:
                    course_names.append(match.group(1))

        return course_names

    # --------------------------------------------------
    # 2. GET ALL SOURCE COURSE NAMES
    # NEW METHOD
    # --------------------------------------------------

    def get_all_course_names(self, batch_name=None):
        """
        Return every matching source course worksheet name.

        batch_name='B1' -> B1 courses only
        batch_name='B2' -> B2 courses only
        batch_name=None -> both batches
        """

        if batch_name is not None:
            batch_name = batch_name.strip().upper()

        if batch_name is None:
            spreadsheet_ids = [
                self.B1_SPREADSHEET_ID,
                self.B2_SPREADSHEET_ID,
            ]
        elif batch_name == "B1":
            spreadsheet_ids = [self.B1_SPREADSHEET_ID]
        elif batch_name == "B2":
            spreadsheet_ids = [self.B2_SPREADSHEET_ID]
        else:
            raise ValueError(
                "Invalid batch name. Use B1, B2, or None."
            )

        course_names = []

        for spreadsheet_id in spreadsheet_ids:
            if not spreadsheet_id:
                raise ValueError(
                    f"Spreadsheet ID is missing for batch {batch_name}."
                )

            spreadsheet = self.client.open_by_key(spreadsheet_id)

            matching_sheets = [
                worksheet.title
                for worksheet in spreadsheet.worksheets()
                if re.match(
                    r"^B[12]P\d+-\d+\s+C\d+\s+-",
                    worksheet.title,
                    re.IGNORECASE,
                )
                and (
                    batch_name is None
                    or worksheet.title.upper().startswith(batch_name)
                )
            ]

            course_names.extend(matching_sheets)

            print(
                f"Spreadsheet {spreadsheet_id}: "
                f"{len(matching_sheets)} course tabs found"
            )

        print(f"Total source course tabs: {len(course_names)}")

        return course_names

    # --------------------------------------------------
    # 3. FIND A COURSE WORKSHEET
    # --------------------------------------------------

    def get_course_sheet(self, course_name):
        """Find a course worksheet in the correct batch spreadsheet."""

        course_name = course_name.strip()

        if course_name.upper().startswith("B1P"):
            spreadsheet_id = self.B1_SPREADSHEET_ID
        elif course_name.upper().startswith("B2P"):
            spreadsheet_id = self.B2_SPREADSHEET_ID
        else:
            raise ValueError(
                "Invalid course name. Course must start with B1P or B2P."
            )

        spreadsheet = self.client.open_by_key(spreadsheet_id)

        for worksheet in spreadsheet.worksheets():
            if worksheet.title.casefold().startswith(
                course_name.casefold()
            ):
                return worksheet

        raise ValueError(
            f"Worksheet '{course_name}' not found in the spreadsheet."
        )

    # --------------------------------------------------
    # 4. READ COURSE RECORDS
    # --------------------------------------------------

    def get_course_records(self, course_name):
        """Return headers and student records for a course."""

        worksheet = self.get_course_sheet(course_name)
        values = worksheet.get_all_values()

        if not values:
            return [], []

        headers = [str(value).strip() for value in values[0]]
        records = []

        for row in values[1:]:
            padded_row = row + [""] * max(
                0, len(headers) - len(row)
            )

            records.append(dict(zip(headers, padded_row)))

        return headers, records

    # --------------------------------------------------
    # 5. EXTRACT WEEK NUMBER
    # --------------------------------------------------

    @staticmethod
    def extract_week_number(column_name):
        """Extract a week number from an assignment column header."""

        match = re.match(
            r"^Week\s+(\d+)",
            str(column_name).strip(),
            re.IGNORECASE,
        )

        return int(match.group(1)) if match else None

    # --------------------------------------------------
    # 6. GET COLUMNS FOR SELECTED WEEKS
    # --------------------------------------------------

    def get_week_columns(self, headers, start_week, end_week):
        """Find assignment columns inside the selected week range."""

        week_columns = {}

        for header in headers:
            week_number = self.extract_week_number(header)

            if (
                week_number is not None
                and start_week <= week_number <= end_week
            ):
                week_columns.setdefault(week_number, []).append(header)

        return week_columns

    # --------------------------------------------------
    # 7. CALCULATE WEEKLY DATA
    # --------------------------------------------------

    def calculate_student_weekly_data(
        self,
        record,
        week_columns,
        start_week,
        end_week,
    ):
        """Calculate assignment totals and preserve each status."""

        assignment_statuses = {}
        total_assigned = 0
        total_submitted = 0
        week_wise_data = {}

        for week_number in range(start_week, end_week + 1):
            columns = week_columns.get(week_number, [])
            submitted_count = 0

            for column in columns:
                status = str(record.get(column, "")).strip()
                assignment_statuses[column] = status

                if status.lower() in {
                    "submitted",
                    "turned in",
                    "returned",
                }:
                    submitted_count += 1

            assigned_count = len(columns)

            total_assigned += assigned_count
            total_submitted += submitted_count

            week_wise_data[f"week_{week_number}"] = {
                "no_of_submitted": submitted_count,
                "no_of_assigned": assigned_count,
            }

        percentage = (
            round(total_submitted / total_assigned * 100, 2)
            if total_assigned
            else 0.0
        )

        return {
            "total_assigned": total_assigned,
            "total_submitted": total_submitted,
            "percentage_submitted": percentage,
            "week_wise_data": week_wise_data,
            "assignment_statuses": assignment_statuses,
        }

    # --------------------------------------------------
    # 8. FIND A STUDENT
    # --------------------------------------------------

    def get_student_data(
        self,
        records,
        week_columns,
        roll_number,
        start_week,
        end_week,
    ):
        """Find a student by roll number and calculate performance."""

        target_roll_number = str(roll_number).strip()

        for record in records:
            record_roll_number = str(
                record.get("Roll Number", "")
            ).strip()

            if record_roll_number == target_roll_number:
                student_data = {
                    "roll_number": record_roll_number,
                    "student_name": record.get("Student Name", ""),
                }

                student_data.update(
                    self.calculate_selected_week_data(
                        record,
                        week_columns,
                        start_week,
                        end_week,
                    )
                )

                return student_data

        return None

    # --------------------------------------------------
    # 9. GET ONE STUDENT'S COURSE DATA
    # --------------------------------------------------

    def get_course_data(
        self,
        course_name,
        roll_number,
        start_week,
        end_week,
    ):
        """Return one student's data for a course and week range."""

        if start_week < 1 or end_week < start_week:
            raise ValueError("Invalid week range.")

        headers, records = self.get_course_records(course_name)

        week_columns = self.get_week_columns(
            headers,
            start_week,
            end_week,
        )

        print("Selected range:", start_week, end_week)
        print("Week columns found:", week_columns)

        return self.get_student_data(
            records,
            week_columns,
            roll_number,
            start_week,
            end_week,
        )

    # --------------------------------------------------
    # 10. GET ALL COURSE DATA FOR A BATCH
    # --------------------------------------------------

    def get_all_course_data(
        self,
        start_week,
        end_week,
        batch_name=None,
    ):
        """
        Collect student records from every selected course tab.

        B1 -> all matching course tabs in the B1 spreadsheet.
        B2 -> all matching course tabs in the B2 spreadsheet.
        None -> both spreadsheets.

        The selected week range controls which assignment
        columns are included in each student's calculations.
        """

        if start_week < 1 or end_week < start_week:
            raise ValueError("Invalid week range.")

        if batch_name is not None:
            batch_name = batch_name.strip().upper()

        if batch_name is None:
            spreadsheet_ids = [
                self.B1_SPREADSHEET_ID,
                self.B2_SPREADSHEET_ID,
            ]
        elif batch_name == "B1":
            spreadsheet_ids = [self.B1_SPREADSHEET_ID]
        elif batch_name == "B2":
            spreadsheet_ids = [self.B2_SPREADSHEET_ID]
        else:
            raise ValueError(
                "Invalid batch name. Use B1, B2, or None."
            )

        all_courses_data = []

        for spreadsheet_id in spreadsheet_ids:
            if not spreadsheet_id:
                raise ValueError(
                    f"Spreadsheet ID is missing for batch {batch_name}."
                )

            spreadsheet = self.client.open_by_key(spreadsheet_id)

            course_sheets = [
                worksheet
                for worksheet in spreadsheet.worksheets()
                if re.match(
                    r"^B[12]P\d+-\d+\s+C\d+\s+-",
                    worksheet.title,
                    re.IGNORECASE,
                )
                and (
                    batch_name is None
                    or worksheet.title.upper().startswith(batch_name)
                )
            ]

            print(
                f"Processing {len(course_sheets)} course tabs "
                f"from spreadsheet {spreadsheet_id}"
            )

            course_data = self.process_course_worksheets(
                spreadsheet,
                course_sheets,
                start_week,
                end_week,
            )

            all_courses_data.extend(course_data)

        print(
            "Total student-course records collected: "
            f"{len(all_courses_data)}"
        )

        return all_courses_data

    # --------------------------------------------------
    # 11. PROCESS ALL COURSE WORKSHEETS
    # --------------------------------------------------

    def process_course_worksheets(
        self,
        spreadsheet,
        course_sheets,
        start_week,
        end_week,
    ):
        """Read selected course tabs and collect student records."""

        all_courses_data = []

        if not course_sheets:
            return all_courses_data

        ranges = [
            f"'{worksheet.title.replace(chr(39), chr(39) * 2)}'!A:ZZ"
            for worksheet in course_sheets
        ]

        # Read all selected course tabs in one batch request.
        response = spreadsheet.values_batch_get(ranges=ranges)
        value_ranges = response.get("valueRanges", [])

        print(
            f"Requested {len(course_sheets)} course tabs; "
            f"Google Sheets returned {len(value_ranges)} value ranges."
        )

        # Process each worksheet and its corresponding response.
        for index, worksheet in enumerate(course_sheets):

            if index >= len(value_ranges):
                print(
                    f"WARNING: No response returned for "
                    f"{worksheet.title}"
                )
                continue

            value_range = value_ranges[index]
            rows = value_range.get("values", [])

            if not rows:
                print(
                    f"WARNING: Source tab is empty: {worksheet.title}"
                )
                continue

            headers = [str(header).strip() for header in rows[0]]

            if "Roll Number" not in headers:
                print(
                    f"WARNING: 'Roll Number' header not found in "
                    f"{worksheet.title}. Headers: {headers}"
                )
                continue

            week_columns = self.get_week_columns(
                headers,
                start_week,
                end_week,
            )

            print(
                f"Reading {worksheet.title}: "
                f"{len(rows) - 1} source rows, "
                f"{sum(len(columns) for columns in week_columns.values())} "
                "selected assignment columns"
            )

            course_record_count = 0

            for row in rows[1:]:
                if not any(str(value).strip() for value in row):
                    continue

                padded_row = row + [""] * max(
                    0,
                    len(headers) - len(row),
                )

                record = dict(zip(headers, padded_row))

                roll_number = str(
                    record.get("Roll Number", "")
                ).strip()

                if not roll_number:
                    continue

                calculation = self.calculate_selected_week_data(
                    record,
                    week_columns,
                    start_week,
                    end_week,
                )

                student_data = {
                    "course_name": worksheet.title,
                    "roll_number": roll_number,
                    "student_name": record.get("Student Name", ""),
                    **calculation,
                }

                all_courses_data.append(student_data)
                course_record_count += 1

            print(
                f"Collected {course_record_count} students from "
                f"{worksheet.title}"
            )

        # This return must stay outside the loop.
        return all_courses_data

    # --------------------------------------------------
    # 12. CALCULATE DATA FOR SELECTED WEEKS
    # --------------------------------------------------

    def calculate_selected_week_data(
        self,
        record,
        week_columns,
        start_week,
        end_week,
    ):
        """Calculate totals for the entire selected week range."""

        assignment_statuses = {}
        total_assigned = 0
        total_submitted = 0
        week_wise_data = {}

        for week_number in range(start_week, end_week + 1):
            columns = week_columns.get(week_number, [])
            submitted_count = 0

            for column in columns:
                status = str(record.get(column, "")).strip()
                assignment_statuses[column] = status

                if status.lower() in {
                    "submitted",
                    "turned in",
                    "returned",
                }:
                    submitted_count += 1

            assigned_count = len(columns)

            total_assigned += assigned_count
            total_submitted += submitted_count

            week_wise_data[f"week_{week_number}"] = {
                "no_of_submitted": submitted_count,
                "no_of_assigned": assigned_count,
            }

        percentage = (
            round(total_submitted / total_assigned * 100, 2)
            if total_assigned
            else 0.0
        )

        return {
            "total_assigned": total_assigned,
            "total_submitted": total_submitted,
            "percentage_submitted": percentage,
            "week_wise_data": week_wise_data,
            "assignment_statuses": assignment_statuses,
        }
