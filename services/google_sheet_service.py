

import gspread
from google.oauth2.service_account import Credentials
import re


class GoogleSheetService:

    SCOPES = [
        "https://www.googleapis.com/auth/spreadsheets"
    ]

    B1_SPREADSHEET_ID = "1-BYM115aHEpauv-cPtS1abMerkPd_i6eTywlzFafVw8"
    B2_SPREADSHEET_ID = "1QQe3-TcwY7r6ELU7xtamnLsiEI9eIUDlVYvwdMNCHVk"


    def __init__(self):

        # Load service account
        self.credentials = Credentials.from_service_account_file(
            "credentials/service_account.json",
            scopes=self.SCOPES
        )

        # Create gspread client
        self.client = gspread.authorize(self.credentials)


    def getAllcoursesTitles(self):
        coursename=[];
        spreadsheetB1= self.client.open_by_key( self.B1_SPREADSHEET_ID )
        spreadsheetB2 = self.client.open_by_key( self.B2_SPREADSHEET_ID )
        
        worksheets1=spreadsheetB1.worksheets()
        worksheets2=spreadsheetB2.worksheets()

        for worksheet in worksheets1:
             
             match = re.match(r"^(B1P\d+-\d+\s+C\d+)\s*-", worksheet.title)
             if match :
               coursename.append(match.group(1))

        for worksheet in worksheets2:
            match = re.match(r"^(B2P\d+-\d+\s+C\d+)\s*-", worksheet.title)
            if match :
              coursename.append(match.group(1))
        return coursename

    def get_all_week_name(self):
        spreadsheetB1 = self.client.open_by_key(self.B1_SPREADSHEET_ID)
        worksheet = spreadsheetB1.worksheets()[1]

        headers = worksheet.get_values("1:1")[0]

        week_names = []

        for header in headers:
           match = re.match(r"^(Week\s+\d+)", header.strip())

           if match:
            week_name = match.group(1)

            if week_name not in week_names:
                week_names.append(week_name)

        return week_names



    def get_course_sheet(self, course_name):

        course_name = course_name.upper()

        # Decide which spreadsheet to use
        if course_name.startswith("B1P"):
            spreadsheet_id = self.B1_SPREADSHEET_ID

        elif course_name.startswith("B2P"):
            spreadsheet_id = self.B2_SPREADSHEET_ID

        else:
            raise ValueError(
                "Invalid course name. Course must start with B1P or B2P."
            )

        # Open the correct spreadsheet
        spreadsheet = self.client.open_by_key(spreadsheet_id)

        worksheets=spreadsheet.worksheets()

        for worksheet in worksheets:
            if worksheet.title.upper().startswith(course_name):
                return worksheet

        raise ValueError(f"Worksheet '{course_name}' not found in the spreadsheet.")



    

    def get_course_records(self, course_name):

        worksheet = self.get_course_sheet(course_name)

        headers = worksheet.get_values("1:1")[0]
        records= worksheet.get_all_records()
        

        return headers, records


    

    def extract_week_number(self,column_name):

        match=re.match(
            r"^Week\s+(\d+)",
            column_name.strip()
        )
        if match:
           return int(match.group(1))

        return None




    def get_week_columns(self, headers, start_week,end_week):
        week_columns = {}

        for header in headers:
        

            match = re.match(r"^Week\s+(\d+)", header.strip())

            if match:
                week_number = int(match.group(1))
             

                if start_week<= week_number <= end_week:
                  if week_number not in week_columns:
                    week_columns[week_number] = []

                  week_columns[week_number].append(header)

        return week_columns


    def calculate_student_weekly_data(self,record,week_columns,start_Week,end_week):

        week_wise_data = {}

        total_assigned=0
        total_submitted=0


        for week_number in range(start_Week,end_week+1):

            assigned_count=0
            submitted_count=0

            colmns =week_columns.get(week_number,[])

            for column in colmns:

                status=str(record.get(column,"")).strip()

                assigned_count+=1

                if status=="Submitted":
                    submitted_count+=1
            total_assigned+=assigned_count
            total_submitted+=submitted_count
            

            week_wise_data[f"week_{week_number}"] = {
                "no_of_submitted":submitted_count,
                "no_of_assigned":assigned_count
            }

        if total_assigned>0:
          percentage_submitted =(
              total_submitted/total_assigned)*100


        else:
         percentage_submitted=0.0

        return{
        
        "total_assigned":total_assigned,
        "total_submitted":total_submitted,
        "percentage_submitted":percentage_submitted,
        "week_wise_data":week_wise_data
    }

    def get_student_data(self,records,week_columns,roll_number,start_week,end_week):

       

        for record in records:
            if(str(record.get("Roll Number").strip())==str(roll_number).strip()):
              
               student_data={
                "roll_number":record.get("Roll Number"),
                "student_name":record.get("Student Name"),
               }

               calculation=self.calculate_student_weekly_data(
                record,
                week_columns,
                start_week,
                end_week
               )
               student_data.update(calculation)
               return student_data
        return None

    

    def get_course_data(self,course_name,roll_number,start_week,end_week):
        
        headers,records = self.get_course_records(course_name)

        week_columns = self.get_week_columns(headers,start_week,end_week)

        student=self.get_student_data(records,week_columns,roll_number,start_week,end_week)

        if student is not None:
           return student
        return None
           

        



