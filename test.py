from services.assignment__service import AssignmentService

from services.google_sheet_service import GoogleSheetService

assignment_service=AssignmentService()

google_sheet_service=GoogleSheetService()



response=assignment_service.get_course_assignments("B1P1","RA2511003010019",5,7)

print(response)


result=google_sheet_service.get_all_course_data(1,9,"B1")

print(len(result))






