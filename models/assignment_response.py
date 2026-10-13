
from pydantic import BaseModel
from typing import Dict


class AssignmentSummary(BaseModel):
    total_submitted: int
    total_assigned: int
    percentage: float

class WeekWiseData(BaseModel):
    no_of_submitted: int
    no_of_assigned: int


class StudentAssignmentData(BaseModel):
    roll_number:str
    student_name:str
    summary:AssignmentSummary
    week_wise_data:Dict[str, WeekWiseData]  # Dictionary with week as key and WeekWiseData as value

class AssignmentResponse(BaseModel):
   success_flag:bool
   course_name:str
   start_week:int
   end_week:int
   student_info:StudentAssignmentData| None=None

   error_message:str|None=None