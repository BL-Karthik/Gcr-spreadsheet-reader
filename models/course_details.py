from pydantic import BaseModel
from typing import List



class CourseDetails(BaseModel):
    courseTiltes :List[str]
    WeekNames:List[str]


