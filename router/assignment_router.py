from fastapi import APIRouter, HTTPException

from services.google_sheet_service import GoogleSheetService
from models.assignment_response import AssignmentResponse
from services.assignment__service import AssignmentService
from fastapi.responses import JSONResponse

assignment_router = APIRouter()
google_sheet_service = GoogleSheetService()
assignment_service = AssignmentService()



@assignment_router.get("/assignments/course/{course_name}/student/{roll_number}/week/{start_week}/{end_week}")
def get_assignments_by_coursename(course_name:str,roll_number:str,start_week :int ,end_week:int):

    if end_week<start_week:
        raise HTTPException(
              status_code=400,
                 detail="End week should greater than start Week")
    if start_week<1 or end_week<1:
        raise HTTPException(
            status_code=400,
            detail="Week Number should be greater than 1 or equal to 1"
        )
    
    response= assignment_service.get_course_assignments(course_name,roll_number,start_week,end_week)

    if response["success_flag"] is False:
        return JSONResponse(
            status_code=404,
            content=response
        )

        
    return AssignmentResponse(
            success_flag=response["success_flag"],
            course_name=response["course_name"],
            start_week=response["start_week"],
            end_week=response["end_week"],
            student_info=response["student_info"],
            error_message=response["error_message"])
        






      

      



    

    
    
  

   

