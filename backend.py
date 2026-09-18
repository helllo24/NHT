import os
from typing import List, Optional
from datetime import date
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, String, Integer, Date, Text, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, relationship, Session

# --- DATABASE CONFIGURATION ---
# Replace with your Aiven MySQL connection string:
# mysql+pymysql://username:password@host:port/database?ssl_ca=...
DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "mysql+pymysql://avnadmin:password@host:port/database?ssl_disabled=false"
)

engine = create_engine(DATABASE_URL)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- SQLALCHEMY MODELS ---
class ProjectModel(Base):
    __tablename__ = "projects"
    
    id = Column(String(50), primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    location = Column(String(100), nullable=True)

class SubmissionModel(Base):
    __tablename__ = "submissions"
    
    id = Column(String(50), primary_key=True, index=True)
    project_id = Column(String(50), index=True)
    project_name = Column(String(255))
    qa_name = Column(String(100))
    location = Column(String(100))
    audit_date = Column(Date)
    agent_name = Column(String(100))
    profile_id = Column(String(100), index=True)
    attempt = Column(Integer)
    score = Column(Integer)
    result = Column(String(100))
    timestamp = Column(String(50))
    
    answers = relationship("SubmissionAnswerModel", cascade="all, delete-orphan")
    reasons = relationship("SubmissionReasonModel", cascade="all, delete-orphan")

class SubmissionAnswerModel(Base):
    __tablename__ = "submission_answers"
    id = Column(Integer, primary_key=True, autoincrement=True)
    submission_id = Column(String(50), ForeignKey("submissions.id"))
    answer = Column(String(50))

class SubmissionReasonModel(Base):
    __tablename__ = "submission_reasons"
    id = Column(Integer, primary_key=True, autoincrement=True)
    submission_id = Column(String(50), ForeignKey("submissions.id"))
    reason = Column(Text, nullable=True)

# Create tables in Aiven MySQL
Base.metadata.create_all(bind=engine)

# --- PYDANTIC SCHEMAS ---
class ProjectCreate(BaseModel):
    id: str
    name: str
    location: Optional[str] = None

class ProjectResponse(ProjectCreate):
    class Config:
        orm_mode = True

class SubmissionCreate(BaseModel):
    id: str
    projectId: str
    projectName: str
    qaName: str
    location: str
    auditDate: date  # Changed from audit_date to auditDate to match frontend
    agentName: str
    profileId: str
    attempt: int
    answers: List[Optional[str]]
    reasons: List[Optional[str]]
    score: int
    result: str
    timestamp: str

# --- DEPENDENCY ---
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- FASTAPI APP ---
app = FastAPI(title="NHT Certification Backend", version="1.0")

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- ENDPOINTS: PROJECTS ---
@app.get("/api/projects", response_model=List[ProjectResponse])
def get_projects(db: Session = Depends(get_db)):
    return db.query(ProjectModel).all()

@app.post("/api/projects", response_model=ProjectResponse)
def create_project(project: ProjectCreate, db: Session = Depends(get_db)):
    db_proj = ProjectModel(id=project.id, name=project.name, location=project.location)
    db.add(db_proj)
    db.commit()
    db.refresh(db_proj)
    return db_proj

# --- ENDPOINTS: SUBMISSIONS ---
@app.get("/api/submissions")
def get_submissions(projectId: Optional[str] = Query(None), db: Session = Depends(get_db)):
    query = db.query(SubmissionModel)
    if projectId:
        query = query.filter(SubmissionModel.project_id == projectId)
    
    subs = query.all()
    # Format back into the exact JSON structure expected by the frontend
    results = []
    for s in subs:
        results.append({
            "id": s.id,
            "projectId": s.project_id,
            "projectName": s.project_name,
            "qaName": s.qa_name,
            "location": s.location,
            "auditDate": str(s.audit_date),
            "agentName": s.agent_name,
            "profileId": s.profile_id,
            "attempt": s.attempt,
            "answers": [a.answer for a in s.answers],
            "reasons": [r.reason for r in s.reasons],
            "score": s.score,
            "result": s.result,
            "timestamp": s.timestamp
        })
    return results

@app.post("/api/submissions")
def create_submission(sub: SubmissionCreate, db: Session = Depends(get_db)):
    db_sub = SubmissionModel(
        id=sub.id,
        project_id=sub.projectId,
        project_name=sub.projectName,
        qa_name=sub.qaName,
        location=sub.location,
        audit_date=sub.auditDate,  # Mapped from sub.auditDate to database column audit_date
        agent_name=sub.agentName,
        profile_id=sub.profileId,
        attempt=sub.attempt,
        score=sub.score,
        result=sub.result,
        timestamp=sub.timestamp
    )
    
    # Add answers mapping
    for ans in sub.answers:
        db_sub.answers.append(SubmissionAnswerModel(answer=ans or ""))
        
    # Add reasons mapping
    for rsn in sub.reasons:
        db_sub.reasons.append(SubmissionReasonModel(reason=rsn or ""))
        
    db.add(db_sub)
    db.commit()
    return {"status": "success", "id": sub.id}

@app.delete("/api/submissions")
def delete_all_submissions(db: Session = Depends(get_db)):
    db.query(SubmissionAnswerModel).delete()
    db.query(SubmissionReasonModel).delete()
    db.query(SubmissionModel).delete()
    db.commit()
    return {"status": "cleared"}

