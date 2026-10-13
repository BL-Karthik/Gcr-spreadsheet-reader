

from services.google_sheet_service import GoogleSheetService


class AssignmentService:

    def __init__(self):
        self.google_sheet_service = GoogleSheetService()

    def get_course_assignments(self,course_name,roll_number,start_week,end_week):

        student = self.google_sheet_service.get_course_data(
            course_name,
            roll_number,
            start_week,end_week)

        
        if student is None:
                return {
                         "success_flag": False,
                         "course_name": course_name,
                         "roll_number":roll_number,
                         "start_week":start_week,
                         "end_week": end_week,
                         "student_info":None,
                         "error_message": "Student Not Found"  }
        

        student_data={
            "roll_number":student["roll_number"],
            "student_name":student["student_name"],
            "summary":{
                "total_submitted":student["total_submitted"],
                "total_assigned":student["total_assigned"],
                "percentage":student["percentage_submitted"]
            },
            "week_wise_data":student["week_wise_data"]
         }

        

        return {
            "success_flag": True,
            "course_name": course_name,
            "roll_number":roll_number,
            "start_week":start_week,
            "end_week": end_week,
            "student_info":student_data ,
            "error_message": None
        }



