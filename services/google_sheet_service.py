
import re
import os
from dotenv import load_dotenv
import gspread
from google.oauth2.service_account import Credentials


class GoogleSheetService:

    SCOPES = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive.file"
    ]



    load_dotenv()

    B1_SPREADSHEET_ID = os.getenv("B1_SPREADSHEET_ID")
    B2_SPREADSHEET_ID = os.getenv("B2_SPREADSHEET_ID")
    def __init__(self):
        """Initialize the authenticated Google Sheets client."""

        self.credentials = Credentials.from_service_account_file(
            "credentials/service_account.json",
            scopes=self.SCOPES
        )

        self.client = gspread.authorize(self.credentials)

    def getAllcoursesTitles(self):
        """Return the course names from B1 and B2."""

        course_names = []

        for spreadsheet_id in (
            self.B1_SPREADSHEET_ID,
            self.B2_SPREADSHEET_ID
        ):
            spreadsheet = self.client.open_by_key(spreadsheet_id)

            for worksheet in spreadsheet.worksheets():
                match = re.match(
                    r"^(B[12]P\d+-\d+\s+C\d+)\s+-",
                    worksheet.title,
                    re.IGNORECASE
                )

                if match:
                    course_names.append(match.group(1))

        return course_names

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

    @staticmethod
    def extract_week_number(column_name):
        """Extract a week number from an assignment column header."""

        match = re.match(
            r"^Week\s+(\d+)",
            str(column_name).strip(),
            re.IGNORECASE
        )

        return int(match.group(1)) if match else None

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

   
    def calculate_student_weekly_data(
           self, record, week_columns, start_week, end_week
):
          """Preserve individual assignment statuses and calculate totals."""

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

                   if status.lower() in {"submitted", "turned in", "returned"}:
                      submitted_count += 1

                      total_assigned += len(columns)
                      total_submitted += submitted_count

                      week_wise_data[f"week_{week_number}"] = {
            "no_of_submitted": submitted_count,
            "no_of_assigned": len(columns)
        }

          percentage = (
        round(total_submitted / total_assigned * 100, 2)
        if total_assigned else 0.0
    )

          return {
        "total_assigned": total_assigned,
        "total_submitted": total_submitted,
        "percentage_submitted": percentage,
        "week_wise_data": week_wise_data,
        "assignment_statuses": assignment_statuses
    }


    def get_student_data(
        self, records, week_columns, roll_number, start_week, end_week
    ):
        """Find a student by roll number and calculate their performance."""

        target_roll_number = str(roll_number).strip()

        for record in records:
            record_roll_number = str(
                record.get("Roll Number", "")
            ).strip()

            if record_roll_number == target_roll_number:
                student_data = {
                    "roll_number": record_roll_number,
                    "student_name": record.get("Student Name", "")
                }

                student_data.update(
                    self.calculate_selected_week_data(
                        record,
                        week_columns,
                        start_week,
                        end_week
                    )
                )

                return student_data

        return None

    def get_course_data(
        self, course_name, roll_number, start_week, end_week
    ):
        """Return one student's data for a course and week range."""

        if start_week < 1 or end_week < start_week:
            raise ValueError("Invalid week range.")

        headers, records = self.get_course_records(course_name)

        week_columns = self.get_week_columns(
            headers, start_week, end_week
        )
        print("Selected range:", start_week, end_week)
        print("Week columns found:", week_columns)   

        return self.get_student_data(
            records,
            week_columns,
            roll_number,
            start_week,
            end_week
        )

    def get_all_course_data(
        self, start_week, end_week, batch_name=None
    ):
        """
        Collect every student from every course tab in B1, B2,
        or both, calculating data only for the selected weeks.
        """

        if start_week < 1 or end_week < start_week:
            raise ValueError("Invalid week range.")

        if batch_name is not None:
            batch_name = batch_name.strip().upper()

        if batch_name is None:
            spreadsheet_ids = [
                self.B1_SPREADSHEET_ID,
                self.B2_SPREADSHEET_ID
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
            spreadsheet = self.client.open_by_key(spreadsheet_id)

            course_sheets = [
                worksheet
                for worksheet in spreadsheet.worksheets()
                if re.match(
                    r"^B[12]P\d+-\d+\s+C\d+\s+-",
                    worksheet.title,
                    re.IGNORECASE
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
                end_week
            )

            all_courses_data.extend(course_data)

        print(
            f"Total student-course records collected: "
            f"{len(all_courses_data)}"
        )

        return all_courses_data

    def process_course_worksheets(
        self, spreadsheet, course_sheets, start_week, end_week
    ):
        """Read every selected course tab and collect all student records."""

        all_courses_data = []

        if not course_sheets:
            return all_courses_data

        ranges = [
            f"'{worksheet.title.replace(chr(39), chr(39) * 2)}'!A:ZZ"
            for worksheet in course_sheets
        ]

        # Read all selected course tabs using one batch request.
        response = spreadsheet.values_batch_get(ranges=ranges)
        value_ranges = response.get("valueRanges", [])

        for worksheet, value_range in zip(course_sheets, value_ranges):
            rows = value_range.get("values", [])

            if not rows:
                continue

            headers = [str(header).strip() for header in rows[0]]

            week_columns = self.get_week_columns(
                headers, start_week, end_week
            )

            for row in rows[1:]:
                if not any(str(value).strip() for value in row):
                    continue

                padded_row = row + [""] * max(
                    0, len(headers) - len(row)
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
                    end_week
                )

                student_data = {
                    "course_name": worksheet.title,
                    "roll_number": roll_number,
                    "student_name": record.get("Student Name", ""),
                    **calculation
                }

                all_courses_data.append(student_data)

        # Keep this return outside both loops.
        return all_courses_data

    
    def calculate_selected_week_data(self, record, week_columns, start_week, end_week):
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
                "returned"
               }:
                 
                 submitted_count += 1

        # Calculate this week's totals after checking all its assignments.
           assigned_count = len(columns)

           total_assigned += assigned_count
           total_submitted += submitted_count

        # Store the result for this week.
           week_wise_data[f"week_{week_number}"] = {
               "no_of_submitted": submitted_count,
                "no_of_assigned": assigned_count}

    # Calculate the percentage after processing every selected week.
        percentage = (
        round(total_submitted / total_assigned * 100, 2)
        if total_assigned
        else 0.0 )

        return {
        "total_assigned": total_assigned,
        "total_submitted": total_submitted,
        "percentage_submitted": percentage,
        "week_wise_data": week_wise_data,
        "assignment_statuses": assignment_statuses
         }
      
    