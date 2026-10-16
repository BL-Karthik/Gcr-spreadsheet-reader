from fastapi import FastAPI
from router.assignment_router import assignment_router
from fastapi.middleware.cors import CORSMiddleware
app=FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173","http://localhost:5174"],

    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

app.include_router(assignment_router)