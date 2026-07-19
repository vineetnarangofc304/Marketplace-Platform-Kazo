"""KAZO Marketplace Finance — FastAPI backend
Modules: auth, masters (commission rules, fixed fee, GT charges, return fee),
uploads (sales & settlement parsers), calculations, reconciliation, dashboards.
"""
from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

import os
import io
import re
import uuid
import logging
import bcrypt
import jwt
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, Literal

from fastapi import FastAPI, APIRouter, HTTPException, Depends, UploadFile, File, Request, Response, Query, status
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field, EmailStr
from bson import ObjectId
import openpyxl

# ---------- Config ----------
JWT_SECRET = os.environ["JWT_SECRET"]
JWT_ALG = "HS256"
ACCESS_TTL_MIN = 60 * 24  # 24h for enterprise usability
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@kazo.com")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("kazo")

app = FastAPI(title="KAZO Marketplace Finance")
api = APIRouter(prefix="/api")


# ---------- Utilities ----------
def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id() -> str:
    return str(uuid.uuid4())


def hash_pwd(pw: str) -> str:
    return bcrypt.hashpw(pw.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_pwd(pw: str, h: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode("utf-8"), h.encode("utf-8"))
    except Exception:
        return False


def create_token(user_id: str, email: str, role: str) -> str:
    payload = {
        "sub": user_id, "email": email, "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TTL_MIN),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)


async def current_user(request: Request) -> Dict[str, Any]:
    token = request.cookies.get("access_token")
    if not token:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
    if not token:
        raise HTTPException(401, "Not authenticated")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid token")
    user = await db.users.find_one({"id": payload["sub"]}, {"password_hash": 0, "_id": 0})
    if not user:
        raise HTTPException(401, "User not found")
    return user


def require_role(*roles: str):
    async def _dep(user=Depends(current_user)):
        if user["role"] not in roles and user["role"] != "admin":
            raise HTTPException(403, f"Requires role: {roles}")
        return user
    return _dep


# ---------- Models ----------
class LoginIn(BaseModel):
    email: str
    password: str


class RegisterIn(BaseModel):
    email: EmailStr
    password: str
    name: str
    role: Literal["admin", "finance", "ops", "viewer"] = "viewer"


class UserOut(BaseModel):
    id: str
    email: str
    name: str
    role: str


# ---------- Auth Routes ----------
@api.post("/auth/login")
async def login(payload: LoginIn, response: Response):
    email = payload.email.strip().lower()
    user = await db.users.find_one({"email": email})
    if not user or not verify_pwd(payload.password, user["password_hash"]):
        raise HTTPException(401, "Invalid credentials")
    token = create_token(user["id"], user["email"], user["role"])
    response.set_cookie(
        "access_token", token, httponly=True, secure=False,
        samesite="lax", max_age=ACCESS_TTL_MIN * 60, path="/",
    )
    return {
        "token": token,
        "user": {"id": user["id"], "email": user["email"], "name": user["name"], "role": user["role"]},
    }


@api.post("/auth/logout")
async def logout(response: Response):
    response.delete_cookie("access_token", path="/")
    return {"ok": True}


@api.get("/auth/me")
async def me(user=Depends(current_user)):
    return {"id": user["id"], "email": user["email"], "name": user["name"], "role": user["role"]}


@api.post("/auth/register")
async def register(payload: RegisterIn, user=Depends(require_role("admin"))):
    email = payload.email.strip().lower()
    if await db.users.find_one({"email": email}):
        raise HTTPException(400, "Email already exists")
    doc = {
        "id": new_id(), "email": email, "name": payload.name,
        "role": payload.role, "password_hash": hash_pwd(payload.password),
        "created_at": now_iso(),
    }
    await db.users.insert_one(doc)
    return {"id": doc["id"], "email": email, "name": payload.name, "role": payload.role}


@api.get("/auth/users")
async def list_users(user=Depends(require_role("admin"))):
    docs = await db.users.find({}, {"password_hash": 0, "_id": 0}).to_list(500)
    return docs


# Include auth router now; other routers imported below
from routers import masters, uploads_r, calculations, reconciliation, dashboards  # noqa: E402

app.include_router(api)
app.include_router(masters.router, prefix="/api")
app.include_router(uploads_r.router, prefix="/api")
app.include_router(calculations.router, prefix="/api")
app.include_router(reconciliation.router, prefix="/api")
app.include_router(dashboards.router, prefix="/api")

# CORS
_origins = os.environ.get("CORS_ORIGINS", "*")
_allow = ["*"] if _origins.strip() == "*" else [o.strip() for o in _origins.split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allow,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def _startup():
    # Indexes
    await db.users.create_index("email", unique=True)
    await db.users.create_index("id", unique=True)
    await db.sales.create_index([("upload_id", 1)])
    await db.sales.create_index([("online_order_id", 1), ("sku", 1)])
    await db.sales.create_index([("order_date", 1)])
    await db.settlement.create_index([("upload_id", 1)])
    await db.settlement.create_index([("online_order_id", 1), ("sku", 1)])
    await db.calculations.create_index([("sales_id", 1)], unique=True)
    await db.discrepancies.create_index([("severity", 1), ("recon_run_id", 1)])
    await db.uploads.create_index([("uploaded_at", -1)])

    # Seed admin
    existing = await db.users.find_one({"email": ADMIN_EMAIL})
    if not existing:
        await db.users.insert_one({
            "id": new_id(), "email": ADMIN_EMAIL, "name": "Administrator",
            "role": "admin", "password_hash": hash_pwd(ADMIN_PASSWORD),
            "created_at": now_iso(),
        })
        logger.info(f"Seeded admin: {ADMIN_EMAIL}")
    elif not verify_pwd(ADMIN_PASSWORD, existing["password_hash"]):
        await db.users.update_one(
            {"email": ADMIN_EMAIL},
            {"$set": {"password_hash": hash_pwd(ADMIN_PASSWORD)}},
        )

    # Seed masters (default Myntra commission structure) if empty
    await masters.seed_defaults(db)


@app.on_event("shutdown")
async def _shutdown():
    client.close()


@app.get("/api/health")
async def health():
    return {"status": "ok", "time": now_iso()}
