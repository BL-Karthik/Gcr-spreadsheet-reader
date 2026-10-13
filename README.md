<h1>GCR Spreadsheet Reader</h1>

<p>A Python-based REST API built with FastAPI to retrieve student assignment submission data from Google Sheets. The API allows users to search for students by course name and roll number, select a week range, and retrieve assignment statistics and week-wise submission details.</p>

<h2>Features</h2>

<ul>
<li>Retrieve course names from B1 and B2 Google Sheets spreadsheets.</li>
<li>Retrieve available assignment week names.</li>
<li>Search for students using their roll numbers.</li>
<li>Filter assignment data by start week and end week.</li>
<li>Calculate total submitted assignments, total assigned assignments, and submission percentage.</li>
<li>Retrieve week-wise assignment statistics.</li>
<li>Validate week ranges and handle missing students.</li>
<li>Explore API endpoints using Swagger UI.</li>
</ul>

<h2>Technology Stack</h2>

<ul>
<li>Python</li>
<li>FastAPI</li>
<li>Google Sheets API</li>
<li>gspread</li>
<li>Google Authentication</li>
<li>Pydantic</li>
<li>Uvicorn</li>
<li>pytest (for automated testing, if configured)</li>
</ul>

<h2>Project Structure</h2>

<pre>
Gcr_spreadsheet_reader/
├── main.py
├── models/
│   ├── __init__.py
│   ├── assignment_response.py
│   └── course_details.py
├── router/
│   └── assignment_router.py
├── services/
│   ├── __init__.py
│   ├── assignment__service.py
│   └── google_sheet_service.py
├── credentials/
│   └── service_account.json
├── test.py
├── requirements.txt
├── .gitignore
└── README.md
</pre>


<h2>Prerequisites</h2>

<ul>
<li>Python 3.10 or later</li>
<li>pip package manager</li>
<li>Google Cloud project with the Google Sheets API enabled</li>
<li>Service account with permission to read the required spreadsheets</li>
</ul>

<h2>Installation and Setup</h2>

<h3>1. Clone the Repository</h3>

<pre>
git clone https://github.com/YOUR_USERNAME/Gcr_spreadsheet_reader.git
cd Gcr_spreadsheet_reader
</pre>


<h3>2. Create a Virtual Environment</h3>

<pre>
python -m venv venv
</pre>

<h3>3. Activate the Virtual Environment</h3>

<p><strong>Windows PowerShell:</strong></p>

<pre>
.\venv\Scripts\Activate.ps1
</pre>

<p><strong>Windows Command Prompt:</strong></p>

<pre>
venv\Scripts\activate.bat
</pre>

<h3>4. Install Dependencies</h3>

<pre>
pip install -r requirements.txt
</pre>

<p>If <code>requirements.txt</code> has not been created yet, install the core dependencies:</p>

<pre>
pip install fastapi uvicorn gspread google-auth pydantic pytest httpx
</pre>

<p>Save the installed dependencies:</p>

<pre>
pip freeze &gt; requirements.txt
</pre>

<h3>5. Configure Google Sheets Access</h3>

<ol>
<li>Enable the Google Sheets API in Google Cloud Console.</li>
<li>Configure a Google service account.</li>
<li>Grant the service account access to the required B1 and B2 spreadsheets.</li>
<li>Store the credentials JSON file locally at <code>credentials/service_account.json</code>, matching the path used by the application.</li>
</ol>

<p><strong>Security:</strong> Never commit service account JSON files, private keys, access tokens, or other secrets to GitHub. If credentials have been exposed, revoke the compromised key and create a replacement.</p>

<h3>6. Run the Application</h3>

<pre>
uvicorn main:app --reload
</pre>

<p>The application will run at <a href="http://127.0.0.1:8000">http://127.0.0.1:8000</a>.</p>

<h2>API Documentation</h2>

<ul>
<li><strong>Swagger UI:</strong> <a href="http://127.0.0.1:8000/docs">http://127.0.0.1:8000/docs</a></li>
<li><strong>ReDoc:</strong> <a href="http://127.0.0.1:8000/redoc">http://127.0.0.1:8000/redoc</a></li>
</ul>

<h2>Assignment API</h2>

<h3>Get Student Assignment Data</h3>

<p><strong>Method:</strong> GET</p>

<pre>
/assignments/course/{course_name}/student/{roll_number}/week/{start_week}/{end_week}
</pre>

<h3>Path Parameters</h3>

<table>
<thead>
<tr>
<th>Parameter</th>
<th>Type</th>
<th>Description</th>
</tr>
</thead>
<tbody>
<tr>
<td>course_name</td>
<td>String</td>
<td>Course identifier, such as B1P3-603 C1</td>
</tr>
<tr>
<td>roll_number</td>
<td>String</td>
<td>Student roll number</td>
</tr>
<tr>
<td>start_week</td>
<td>Integer</td>
<td>First week to retrieve</td>
</tr>
<tr>
<td>end_week</td>
<td>Integer</td>
<td>Last week to retrieve</td>
</tr>
</tbody>
</table>

<h3>Example Request</h3>

<pre>
GET /assignments/course/B1P3-603%20C1/student/123456/week/5/7
</pre>

<p>Replace <code>123456</code> with a roll number present in the selected course worksheet.</p>

<h3>Successful Response</h3>

<pre>
{
  "success_flag": true,
  "course_name": "B1P3-603 C1",
  "start_week": 5,
  "end_week": 7,
  "student_info": {
    "roll_number": "123456",
    "student_name": "Example Student",
    "summary": {
      "total_submitted": 2,
      "total_assigned": 6,
      "percentage": 33.33
    },
    "week_wise_data": {
      "week_5": {
        "no_of_submitted": 1,
        "no_of_assigned": 2
      },
      "week_6": {
        "no_of_submitted": 1,
        "no_of_assigned": 2
      },
      "week_7": {
        "no_of_submitted": 0,
        "no_of_assigned": 2
      }
    }
  },
  "error_message": null
}
</pre>

<p><em>Note: The student details and submission counts above are sample values for documentation purposes.</em></p>

<h2>Error Handling</h2>

<h3>Student Not Found</h3>

<p><strong>HTTP Status:</strong> 404 Not Found</p>

<pre>
{
  "success_flag": false,
  "course_name": "B1P3-603 C1",
  "roll_number": "123456",
  "start_week": 5,
  "end_week": 7,
  "student_info": null,
  "error_message": "Student Not Found"
}
</pre>

<h3>Invalid Week Range</h3>

<p><strong>HTTP Status:</strong> 400 Bad Request</p>

<p>Returned when the end week is earlier than the start week.</p>

<h3>Invalid Week Number</h3>

<p><strong>HTTP Status:</strong> 400 Bad Request</p>

<p>Week numbers must be greater than or equal to 1.</p>

<h2>How It Works</h2>

<ol>
<li>The client sends the course name, student roll number, and requested week range.</li>
<li>The FastAPI router validates the requested week range.</li>
<li><code>AssignmentService</code> requests student assignment data from <code>GoogleSheetService</code>.</li>
<li><code>GoogleSheetService</code> selects the B1 or B2 spreadsheet based on the course identifier.</li>
<li>The service locates the matching course worksheet and reads its headers and student records.</li>
<li>Assignment columns are grouped by week number.</li>
<li>The service calculates submitted assignments, assigned assignments, and submission percentage.</li>
<li>Pydantic validates the response structure.</li>
<li>FastAPI returns the result as JSON.</li>
</ol>

<h2>Submission Calculation</h2>

<p>The submission percentage is calculated using the following formula:</p>

<pre>
Submission Percentage =
    (Total Submitted / Total Assigned) * 100
</pre>

<p>If no assignments are assigned in the requested week range, the percentage is set to <code>0.0</code>.</p>

<p>The current implementation counts an assignment as submitted only when its status exactly matches <code>Submitted</code>.</p>

<h2>Validation Rules</h2>

<ul>
<li>The start week must be greater than or equal to 1.</li>
<li>The end week must be greater than or equal to the start week.</li>
<li>The roll number is treated as a string.</li>
<li>The course identifier must begin with B1P or B2P.</li>
<li>The student must exist in the selected course worksheet.</li>
</ul>

<h2>Running Tests</h2>

<p>If <code>test.py</code> contains pytest-compatible tests, run:</p>

<pre>
pytest test.py
</pre>

<p>To run all pytest tests:</p>

<pre>
pytest
</pre>

<h2>Security and Configuration</h2>

<ul>
<li>Keep service account credentials outside source control.</li>
<li>Use <code>.gitignore</code> to exclude local credentials and generated files.</li>
<li>Grant spreadsheet access only to authorized service accounts.</li>
<li>Avoid logging sensitive student information or authentication details.</li>
<li>Use environment variables or a secure secret manager for deployment configuration.</li>
</ul>

<p>Example <code>.gitignore</code> entries:</p>

<pre>
venv/
__pycache__/
*.py[cod]
.env
credentials/
.pytest_cache/
</pre>

<h2>Current Limitations</h2>

<ul>
<li>Student assignment data is retrieved directly from Google Sheets.</li>
<li>The current implementation reads worksheet records before finding the requested student, which may affect performance on large worksheets.</li>
<li>The API depends on Google Sheets availability and service account permissions.</li>
<li>Only the exact status <code>Submitted</code> is counted as submitted.</li>
</ul>

<h2>Future Improvements</h2>

<ul>
<li>Improve student lookup performance and reduce unnecessary spreadsheet reads.</li>
<li>Add automated tests for valid requests, invalid week ranges, and missing students.</li>
<li>Improve error handling for Google Sheets authentication failures, missing worksheets, and API quota errors.</li>
<li>Add structured logging and environment-based configuration.</li>
<li>Integrate a frontend for viewing student assignment reports.</li>
</ul>

<h2>Author</h2>

<p><strong>Karthik Reddy Indukuri</strong></p>

<p>GitHub: <a href="https://github.com/BL-Karthik">BL-Karthik</a></p>

<hr>

<p>This project provides a REST API for retrieving and summarizing student assignment submission data stored in Google Sheets.</p>
