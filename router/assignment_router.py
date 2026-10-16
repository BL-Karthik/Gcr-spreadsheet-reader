from fastapi import APIRouter, HTTPException

from services.google_sheet_service import GoogleSheetService
from models.assignment_response import AssignmentResponse
from services.assignment__service import AssignmentService
from fastapi.responses import JSONResponse
from fastapi import HTTPException, Query
from services.google_sheet_service import GoogleSheetService
from services.report_service import ReportService

assignment_router = APIRouter()
assignment_service = AssignmentService()
google_sheet_service = GoogleSheetService()
report_service = ReportService(google_sheet_service)




@assignment_router.get("/assignments/batch/{batch_name}/student/{roll_number}/week/{start_week}/{end_week}")
def get_assignments_by_coursename(batch_name:str,roll_number:str,start_week :int ,end_week:int):

    if end_week<start_week:
        raise HTTPException(
              status_code=400,
                 detail="End week should greater than start Week")
    if start_week<1 or end_week<1:
        raise HTTPException(
            status_code=400,
            detail="Week Number should be greater than 1 or equal to 1"
        )
    
    response= assignment_service.get_course_assignments(batch_name,roll_number,start_week,end_week)

    if response["success_flag"] is False:
        return JSONResponse(
            status_code=404,
            content=response
        )

        
    return AssignmentResponse(
            success_flag=response["success_flag"],
            batch_name=response["course_name"],
            start_week=response["start_week"],
            end_week=response["end_week"],
            student_info=response["student_info"],
            error_message=response["error_message"])
        

@assignment_router.get("/assignments/report/{batch_name}/week/{start_week}/{end_week}")
def generate_assignment_report(
   batch_name:str,start_week :int ,end_week:int,
    share_with_email: str | None = Query(default=None)
):
    if end_week < start_week:
        raise HTTPException(
            status_code=400,
            detail="End week must be greater than or equal to start week."
        )

    try:
        # Step 1: Collect data from the selected courses.
        all_course_data = google_sheet_service.get_all_course_data(
            start_week=start_week,
            end_week=end_week,
            batch_name=batch_name
        )

        if not all_course_data:
            raise HTTPException(
                status_code=404,
                detail="No student assignment data found."
            )

        # Step 2: Create the Google Sheet report.
        report = report_service.export_course_data_to_sheet(
            all_course_data=all_course_data,
            start_week=start_week,
            end_week=end_week,
            batch_name=batch_name,
            share_with_email=share_with_email
        )

        # Step 3: Return the report details and URL.
        return {
            "success_flag": True,
            "message": "Assignment report generated successfully.",
            **report
        }

    except HTTPException:
         raise

    except Exception as exc:
           import traceback
           traceback.print_exc()

           raise HTTPException(
           status_code=500,
           detail=f"Report generation failed: {repr(exc)}")  



