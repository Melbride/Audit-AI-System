from fastapi import FastAPI, HTTPException, UploadFile, File, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from typing import Optional, Literal
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
import shutil
import os
import sys
import secrets

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND_DIR = os.path.join(BASE_DIR, "backend")
if BACKEND_DIR not in sys.path:
    sys.path.append(BACKEND_DIR)

from database import get_db, init_db

app = FastAPI(title="AuditIQ API", debug=True)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── SECURITY CONFIG ───────────────────────────────────────────────────────────
SECRET_KEY = "auditiq-secret-key-change-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 8
pwd_context = CryptContext(schemes=["sha256_crypt"], deprecated="auto")

# ── DATABASE CONNECTION ───────────────────────────────────────────────────────
# ── MODELS ────────────────────────────────────────────────────────────────────
class Client(BaseModel):
    company_name: str
    contact_person: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    industry: Optional[str] = None
    address: Optional[str] = None
    status: Optional[str] = "Active"
    kra_pin: Literal[True, False] = False

class User(BaseModel):
    full_name: str
    email: str
    password: str
    phone: Optional[str] = None
    role: Literal["Admin", "Senior Auditor", "Auditor", "Accountant"]
    assigned_client_id: Optional[int] = None
    status: Optional[str] = "Active"

class UserUpdate(BaseModel):
    full_name: str
    email: str
    phone: Optional[str] = None
    role: Literal["Admin", "Senior Auditor", "Auditor", "Accountant"]
    assigned_client_id: Optional[int] = None
    status: Optional[str] = "Active"

class LoginRequest(BaseModel):
    email: str
    password: str

class PasswordResetRequest(BaseModel):
    email: str

class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str

# ── HELPERS ───────────────────────────────────────────────────────────────────
def hash_password(password: str):
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str):
    return pwd_context.verify(plain, hashed)

def create_token(data: dict):
    expire = datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    data.update({"exp": expire})
    return jwt.encode(data, SECRET_KEY, algorithm=ALGORITHM)

@app.on_event("startup")
def startup_event():
    init_db()

# ── CLIENTS ───────────────────────────────────────────────────────────────────
@app.get("/clients")
def get_clients(db=Depends(get_db)):
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM clients")
    return cursor.fetchall()

@app.get("/clients/{client_id}")
def get_client(client_id: int, db=Depends(get_db)):
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM clients WHERE client_id = %s", (client_id,))
    client = cursor.fetchone()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return client

@app.post("/clients")
def create_client(c: Client, db=Depends(get_db)):
    cursor = db.cursor()
    cursor.execute(
        """INSERT INTO clients (company_name, contact_person, email, phone, industry, address, status, kra_pin)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
        (c.company_name, c.contact_person, c.email, c.phone, c.industry, c.address, c.status, c.kra_pin)
    )
    db.commit()
    return {"client_id": cursor.lastrowid, "message": "Client created"}

@app.put("/clients/{client_id}")
def update_client(client_id: int, c: Client, db=Depends(get_db)):
    cursor = db.cursor()
    cursor.execute(
        """UPDATE clients SET company_name=%s, contact_person=%s, email=%s,
           phone=%s, industry=%s, address=%s, status=%s, kra_pin=%s WHERE client_id=%s""",
        (c.company_name, c.contact_person, c.email, c.phone, c.industry, c.address, c.status, c.kra_pin, client_id)
    )
    db.commit()
    return {"message": "Client updated"}

@app.delete("/clients/{client_id}")
def delete_client(client_id: int, db=Depends(get_db)):
    cursor = db.cursor()
    cursor.execute("DELETE FROM clients WHERE client_id = %s", (client_id,))
    db.commit()
    return {"message": "Client deleted"}

# ── USERS ─────────────────────────────────────────────────────────────────────
@app.get("/users")
def get_users(db=Depends(get_db)):
    cursor = db.cursor(dictionary=True)
    cursor.execute("""
        SELECT u.user_id, u.full_name, u.email, u.phone, u.role, u.status,
               u.assigned_client_id, u.created_at, c.company_name
        FROM users u
        LEFT JOIN clients c ON u.assigned_client_id = c.client_id
    """)
    return cursor.fetchall()

@app.get("/users/{user_id}")
def get_user(user_id: int, db=Depends(get_db)):
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
    user = cursor.fetchone()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.pop("password_hash", None)
    return user

@app.post("/users")
def create_user(u: User, db=Depends(get_db)):
    hashed = hash_password(u.password)
    cursor = db.cursor()
    try:
        cursor.execute(
            """INSERT INTO users (full_name, email, password_hash, phone, role, assigned_client_id, status)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (u.full_name, u.email, hashed, u.phone, u.role, u.assigned_client_id, u.status)
        )
        db.commit()
        return {"user_id": cursor.lastrowid, "message": "User created"}
    except Exception:
        raise HTTPException(status_code=400, detail="Email already exists")

@app.put("/users/{user_id}")
def update_user(user_id: int, u: UserUpdate, db=Depends(get_db)):
    cursor = db.cursor()
    cursor.execute(
        """UPDATE users SET full_name=%s, email=%s, phone=%s,
           role=%s, assigned_client_id=%s, status=%s WHERE user_id=%s""",
        (u.full_name, u.email, u.phone, u.role, u.assigned_client_id, u.status, user_id)
    )
    db.commit()
    return {"message": "User updated"}

@app.delete("/users/{user_id}")
def delete_user(user_id: int, db=Depends(get_db)):
    cursor = db.cursor()
    cursor.execute("DELETE FROM users WHERE user_id = %s", (user_id,))
    db.commit()
    return {"message": "User deleted"}

@app.put("/users/{user_id}/assign/{client_id}")
def assign_user_to_client(user_id: int, client_id: int, db=Depends(get_db)):
    cursor = db.cursor()
    cursor.execute(
        "UPDATE users SET assigned_client_id=%s WHERE user_id=%s",
        (client_id, user_id)
    )
    db.commit()
    return {"message": "User assigned to client"}

# ── AUTH ──────────────────────────────────────────────────────────────────────
@app.post("/auth/login")
def login(req: LoginRequest, db=Depends(get_db)):
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE email = %s", (req.email,))
    user = cursor.fetchone()

    if not user or not verify_password(req.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if user["status"] != "Active":
        raise HTTPException(status_code=403, detail="Account is inactive")

    token = create_token({
        "user_id": user["user_id"],
        "email": user["email"],
        "role": user["role"]
    })

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "user_id": user["user_id"],
            "full_name": user["full_name"],
            "email": user["email"],
            "role": user["role"]
        }
    }

@app.post("/auth/password-reset-request")
def password_reset_request(req: PasswordResetRequest, db=Depends(get_db)):
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE email = %s", (req.email,))
    user = cursor.fetchone()
    if not user:
        raise HTTPException(status_code=404, detail="Email not found")

    token = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(hours=1)

    cursor2 = db.cursor()
    cursor2.execute(
        "INSERT INTO password_resets (user_id, token, expires_at) VALUES (%s, %s, %s)",
        (user["user_id"], token, expires_at)
    )
    db.commit()
    return {"message": "Password reset token generated", "token": token}

@app.post("/auth/password-reset-confirm")
def password_reset_confirm(req: PasswordResetConfirm, db=Depends(get_db)):
    cursor = db.cursor(dictionary=True)
    cursor.execute(
        "SELECT * FROM password_resets WHERE token = %s AND expires_at > NOW()",
        (req.token,)
    )
    reset = cursor.fetchone()
    if not reset:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    hashed = hash_password(req.new_password)
    cursor2 = db.cursor()
    cursor2.execute(
        "UPDATE users SET password_hash = %s WHERE user_id = %s",
        (hashed, reset["user_id"])
    )
    cursor2.execute("DELETE FROM password_resets WHERE token = %s", (req.token,))
    db.commit()
    return {"message": "Password reset successful"}
# ── COLUMN MAPPINGS ───────────────────────────────────────────────────────────
class ColumnMapping(BaseModel):
    client_id: str
    file_type: Optional[str] = "general"
    original_column: str
    mapped_to: str
    confirmed_by: Optional[str] = None

@app.get("/column-mappings")
def get_all_mappings(db=Depends(get_db)):
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM column_mappings")
    return cursor.fetchall()

@app.get("/column-mappings/{client_id}")
def get_client_mappings(client_id: str, db=Depends(get_db)):
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM column_mappings WHERE client_id = %s", (client_id,))
    return cursor.fetchall()

@app.post("/column-mappings")
def create_mapping(m: ColumnMapping, db=Depends(get_db)):
    cursor = db.cursor()
    cursor.execute(
        """INSERT INTO column_mappings (client_id, file_type, original_column, mapped_to, confirmed_by)
           VALUES (%s, %s, %s, %s, %s)""",
        (m.client_id, m.file_type, m.original_column, m.mapped_to, m.confirmed_by)
    )
    db.commit()
    return {"id": cursor.lastrowid, "message": "Column mapping created"}

@app.put("/column-mappings/{mapping_id}")
def update_mapping(mapping_id: int, m: ColumnMapping, db=Depends(get_db)):
    cursor = db.cursor()
    cursor.execute(
        """UPDATE column_mappings SET client_id=%s, file_type=%s, original_column=%s,
           mapped_to=%s, confirmed_by=%s WHERE id=%s""",
        (m.client_id, m.file_type, m.original_column, m.mapped_to, m.confirmed_by, mapping_id)
    )
    db.commit()
    return {"message": "Column mapping updated"}

@app.delete("/column-mappings/{mapping_id}")
def delete_mapping(mapping_id: int, db=Depends(get_db)):
    cursor = db.cursor()
    cursor.execute("DELETE FROM column_mappings WHERE id = %s", (mapping_id,))
    db.commit()
    return {"message": "Column mapping deleted"}
# ── ENGAGEMENTS ───────────────────────────────────────────────────────────────
class Engagement(BaseModel):
    client_id: int
    engagement_name: str
    financial_year: str
    status: Optional[str] = "Planning"
    start_date: Optional[str] = None
    end_date: Optional[str] = None

class EngagementTeam(BaseModel):
    engagement_id: int
    user_id: int
    role: str

class AuditSection(BaseModel):
    engagement_id: int
    section_name: str
    status: Optional[str] = "Pending"
    assigned_to: Optional[int] = None

# ── ENGAGEMENT ROUTES ─────────────────────────────────────────────────────────
@app.get("/engagements")
def get_engagements(db=Depends(get_db)):
    cursor = db.cursor(dictionary=True)
    cursor.execute("""
        SELECT e.*, c.company_name
        FROM engagements e
        LEFT JOIN clients c ON e.client_id = c.client_id
        ORDER BY e.created_at DESC
    """)
    return cursor.fetchall()

@app.get("/engagements/{engagement_id}")
def get_engagement(engagement_id: int, db=Depends(get_db)):
    cursor = db.cursor(dictionary=True)
    cursor.execute("""
        SELECT e.*, c.company_name
        FROM engagements e
        LEFT JOIN clients c ON e.client_id = c.client_id
        WHERE e.engagement_id = %s
    """, (engagement_id,))
    engagement = cursor.fetchone()
    if not engagement:
        raise HTTPException(status_code=404, detail="Engagement not found")
    return engagement

@app.post("/engagements")
def create_engagement(e: Engagement, db=Depends(get_db)):
    cursor = db.cursor()
    cursor.execute(
        """INSERT INTO engagements (client_id, engagement_name, financial_year, status, start_date, end_date)
           VALUES (%s, %s, %s, %s, %s, %s)""",
        (e.client_id, e.engagement_name, e.financial_year, e.status, e.start_date, e.end_date)
    )
    engagement_id = cursor.lastrowid

    # Auto create default audit sections
    default_sections = ["Revenue", "Expenses", "Inventory", "Cash & Bank"]
    for section in default_sections:
        cursor.execute(
            "INSERT INTO audit_sections (engagement_id, section_name) VALUES (%s, %s)",
            (engagement_id, section)
        )
    db.commit()
    return {"engagement_id": engagement_id, "message": "Engagement created with default audit sections"}

@app.put("/engagements/{engagement_id}")
def update_engagement(engagement_id: int, e: Engagement, db=Depends(get_db)):
    cursor = db.cursor()
    cursor.execute(
        """UPDATE engagements SET client_id=%s, engagement_name=%s, financial_year=%s,
           status=%s, start_date=%s, end_date=%s WHERE engagement_id=%s""",
        (e.client_id, e.engagement_name, e.financial_year, e.status, e.start_date, e.end_date, engagement_id)
    )
    db.commit()
    return {"message": "Engagement updated"}

@app.delete("/engagements/{engagement_id}")
def delete_engagement(engagement_id: int, db=Depends(get_db)):
    cursor = db.cursor()
    cursor.execute("DELETE FROM audit_sections WHERE engagement_id = %s", (engagement_id,))
    cursor.execute("DELETE FROM engagement_team WHERE engagement_id = %s", (engagement_id,))
    cursor.execute("DELETE FROM engagements WHERE engagement_id = %s", (engagement_id,))
    db.commit()
    return {"message": "Engagement deleted"}

# ── ENGAGEMENT TEAM ROUTES ────────────────────────────────────────────────────
@app.get("/engagements/{engagement_id}/team")
def get_engagement_team(engagement_id: int, db=Depends(get_db)):
    cursor = db.cursor(dictionary=True)
    cursor.execute("""
        SELECT et.*, u.full_name, u.email, u.role
        FROM engagement_team et
        LEFT JOIN users u ON et.user_id = u.user_id
        WHERE et.engagement_id = %s
    """, (engagement_id,))
    return cursor.fetchall()

@app.post("/engagements/{engagement_id}/team")
def add_team_member(engagement_id: int, t: EngagementTeam, db=Depends(get_db)):
    cursor = db.cursor()
    cursor.execute(
        "INSERT INTO engagement_team (engagement_id, user_id, role) VALUES (%s, %s, %s)",
        (engagement_id, t.user_id, t.role)
    )
    db.commit()
    return {"team_id": cursor.lastrowid, "message": "Team member added"}

@app.delete("/engagements/{engagement_id}/team/{user_id}")
def remove_team_member(engagement_id: int, user_id: int, db=Depends(get_db)):
    cursor = db.cursor()
    cursor.execute(
        "DELETE FROM engagement_team WHERE engagement_id=%s AND user_id=%s",
        (engagement_id, user_id)
    )
    db.commit()
    return {"message": "Team member removed"}

# ── AUDIT SECTIONS ROUTES ─────────────────────────────────────────────────────
@app.get("/engagements/{engagement_id}/sections")
def get_audit_sections(engagement_id: int, db=Depends(get_db)):
    cursor = db.cursor(dictionary=True)
    cursor.execute("""
        SELECT s.*, u.full_name as assigned_to_name
        FROM audit_sections s
        LEFT JOIN users u ON s.assigned_to = u.user_id
        WHERE s.engagement_id = %s
    """, (engagement_id,))
    return cursor.fetchall()

@app.post("/engagements/{engagement_id}/sections")
def add_audit_section(engagement_id: int, s: AuditSection, db=Depends(get_db)):
    cursor = db.cursor()
    cursor.execute(
        "INSERT INTO audit_sections (engagement_id, section_name, status, assigned_to) VALUES (%s, %s, %s, %s)",
        (engagement_id, s.section_name, s.status, s.assigned_to)
    )
    db.commit()
    return {"section_id": cursor.lastrowid, "message": "Audit section added"}

@app.put("/audit-sections/{section_id}")
def update_audit_section(section_id: int, s: AuditSection, db=Depends(get_db)):
    cursor = db.cursor()
    cursor.execute(
        "UPDATE audit_sections SET section_name=%s, status=%s, assigned_to=%s WHERE section_id=%s",
        (s.section_name, s.status, s.assigned_to, section_id)
    )
    db.commit()
    return {"message": "Audit section updated"}

@app.delete("/audit-sections/{section_id}")
def delete_audit_section(section_id: int, db=Depends(get_db)):
    cursor = db.cursor()
    cursor.execute("DELETE FROM audit_sections WHERE section_id = %s", (section_id,))
    db.commit()
    return {"message": "Audit section deleted"}
# ── SUBMISSIONS ───────────────────────────────────────────────────────────────
class Submission(BaseModel):
    engagement_id: int
    section_id: int
    submitted_by: int
    status: Optional[str] = "Draft"
    notes: Optional[str] = None

class SubmissionStatus(BaseModel):
    status: Literal["Draft", "Submitted", "Under Review", "Changes Requested", "Approved"]
    notes: Optional[str] = None

class Notification(BaseModel):
    user_id: int
    message: str
    type: Optional[str] = "engagement_alert"

@app.get("/submissions")
def get_all_submissions(db=Depends(get_db)):
    cursor = db.cursor(dictionary=True)
    cursor.execute("""
        SELECT s.*, u.full_name as submitted_by_name,
               e.engagement_name, sec.section_name
        FROM submissions s
        LEFT JOIN users u ON s.submitted_by = u.user_id
        LEFT JOIN engagements e ON s.engagement_id = e.engagement_id
        LEFT JOIN audit_sections sec ON s.section_id = sec.section_id
        ORDER BY s.created_at DESC
    """)
    return cursor.fetchall()

@app.get("/submissions/{submission_id}")
def get_submission(submission_id: int, db=Depends(get_db)):
    cursor = db.cursor(dictionary=True)
    cursor.execute("""
        SELECT s.*, u.full_name as submitted_by_name,
               e.engagement_name, sec.section_name
        FROM submissions s
        LEFT JOIN users u ON s.submitted_by = u.user_id
        LEFT JOIN engagements e ON s.engagement_id = e.engagement_id
        LEFT JOIN audit_sections sec ON s.section_id = sec.section_id
        WHERE s.submission_id = %s
    """, (submission_id,))
    submission = cursor.fetchone()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    return submission

@app.post("/submissions")
def create_submission(s: Submission, db=Depends(get_db)):
    cursor = db.cursor()
    cursor.execute(
        """INSERT INTO submissions (engagement_id, section_id, submitted_by, status, notes)
           VALUES (%s, %s, %s, %s, %s)""",
        (s.engagement_id, s.section_id, s.submitted_by, s.status, s.notes)
    )
    submission_id = cursor.lastrowid

    if s.status == "Submitted":

        cursor.execute("""
            SELECT e.engagement_name, sec.section_name
            FROM engagements e
            LEFT JOIN audit_sections sec ON sec.engagement_id = e.engagement_id
            WHERE e.engagement_id = %s AND sec.section_id = %s
        """, (s.engagement_id, s.section_id))
        info = cursor.fetchone()
        if info:
            message = f"{info['section_name']} for {info['engagement_name']} is ready for review"
            cursor.execute("""
                SELECT u.user_id FROM users u
                INNER JOIN engagement_team et ON u.user_id = et.user_id
                WHERE et.engagement_id = %s
                AND u.role IN ('Senior Auditor', 'Auditor')
            """, (s.engagement_id,))
            auditors = cursor.fetchall()
            for auditor in auditors:
                cursor.execute(
                    "INSERT INTO notifications (user_id, message, type) VALUES (%s, %s, %s)",
                    (auditor['user_id'], message, 'engagement_alert')
                )
    db.commit()
    return {"submission_id": submission_id, "message": "Submission created"}

@app.put("/submissions/{submission_id}/status")
def update_submission_status(submission_id: int, s: SubmissionStatus, db=Depends(get_db)):
    cursor = db.cursor()
    cursor.execute(
        "UPDATE submissions SET status=%s, notes=%s WHERE submission_id=%s",
        (s.status, s.notes, submission_id)
    )
    db.commit()
    return {"message": f"Submission status updated to {s.status}"}

@app.delete("/submissions/{submission_id}")
def delete_submission(submission_id: int, db=Depends(get_db)):
    cursor = db.cursor()
    cursor.execute("DELETE FROM submissions WHERE submission_id = %s", (submission_id,))
    db.commit()
    return {"message": "Submission deleted"}

# ── NOTIFICATIONS ─────────────────────────────────────────────────────────────
@app.get("/notifications/{user_id}")
def get_user_notifications(user_id: int, db=Depends(get_db)):
    cursor = db.cursor(dictionary=True)
    cursor.execute(
        "SELECT * FROM notifications WHERE user_id = %s ORDER BY created_at DESC",
        (user_id,)
    )
    return cursor.fetchall()

@app.get("/notifications/{user_id}/unread")
def get_unread_notifications(user_id: int, db=Depends(get_db)):
    cursor = db.cursor(dictionary=True)
    cursor.execute(
        "SELECT * FROM notifications WHERE user_id = %s AND is_read = FALSE ORDER BY created_at DESC",
        (user_id,)
    )
    return cursor.fetchall()

@app.put("/notifications/{notification_id}/read")
def mark_notification_read(notification_id: int, db=Depends(get_db)):
    cursor = db.cursor()
    cursor.execute(
        "UPDATE notifications SET is_read = TRUE WHERE notification_id = %s",
        (notification_id,)
    )
    db.commit()
    return {"message": "Notification marked as read"}

@app.put("/notifications/{user_id}/read-all")
def mark_all_read(user_id: int, db=Depends(get_db)):
    cursor = db.cursor()
    cursor.execute(
        "UPDATE notifications SET is_read = TRUE WHERE user_id = %s",
        (user_id,)
    )
    db.commit()
    return {"message": "All notifications marked as read"}


            
# ── FILE UPLOAD ───────────────────────────────────────────────────────────────
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@app.post("/clients/{client_id}/upload")
def upload_file(client_id: int, file: UploadFile = File(...), db=Depends(get_db)):
    allowed_types = ["xlsx", "xls", "csv", "pdf", "tiff", "tif", "jpg", "jpeg", "png", "xml", "json", "txt"]
    file_ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""

    if file_ext not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail="File format not allowed. Accepted: Excel (.xlsx, .xls), CSV (.csv), PDF (.pdf), Scanned (.jpg, .png, .tiff), ERP (.xml, .json, .txt)"
        )

    file_path = f"{UPLOAD_DIR}/{client_id}_{file.filename}"
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    cursor = db.cursor()
    cursor.execute(
        "INSERT INTO uploads (client_id, file_name, file_type, file_path) VALUES (%s, %s, %s, %s)",
        (client_id, file.filename, file_ext.upper(), file_path)
    )
    db.commit()
    return {"file_id": cursor.lastrowid, "filename": file.filename, "type": file_ext.upper(), "message": "File uploaded successfully"}

@app.get("/clients/{client_id}/files")
def get_client_files(client_id: int, db=Depends(get_db)):
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM uploads WHERE client_id = %s", (client_id,))
    return cursor.fetchall()

# This endpoint is for admin use to view all uploaded files across clients. In production, this should be protected and paginated.
@app.get("/files")
def get_all_files(db=Depends(get_db)):
    cursor = db.cursor(dictionary=True)
    cursor.execute("""
        SELECT f.*, c.company_name
        FROM uploads f
        LEFT JOIN clients c ON f.client_id = c.client_id
        ORDER BY f.upload_date DESC
    """)
    return cursor.fetchall()

# ── RUN ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("Audit:app", host="0.0.0.0", port=8000, reload=True)
