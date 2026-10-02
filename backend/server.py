from fastapi import FastAPI, APIRouter, HTTPException, Request, Response, Depends
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field, EmailStr, field_validator
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
import os, uuid, secrets, bcrypt, logging, time, re, io, csv
from bson import ObjectId
import cloudinary, cloudinary.utils, cloudinary.uploader
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")
client = AsyncIOMotorClient(os.environ["MONGO_URL"])
db = client[os.environ["DB_NAME"]]
app = FastAPI(title="AssetFlow Campus API")
api = APIRouter(prefix="/api")
logger = logging.getLogger("assetflow")

cloudinary.config(
    cloud_name=os.environ.get("CLOUDINARY_CLOUD_NAME"),
    api_key=os.environ.get("CLOUDINARY_API_KEY"),
    api_secret=os.environ.get("CLOUDINARY_API_SECRET"),
    secure=True,
)

class Signup(BaseModel):
    name: str
    email: EmailStr
    password: str = Field(min_length=6)

class Login(BaseModel):
    email: EmailStr
    password: str

class AssetCreate(BaseModel):
    name: str
    category: str
    location: str
    department: str
    status: str = "Available"
    serial: str = ""
    bookable: bool = False
    # --- Detailed registration fields (optional, non-breaking) ---
    supplier: str = ""
    purchase_cost: float = 0
    purchase_date: str = ""
    warranty_end: str = ""
    amc_provider: str = ""
    notes: str = ""

class AssetUpdate(BaseModel):
    name: Optional[str] = None
    location: Optional[str] = None
    status: Optional[str] = None
    department: Optional[str] = None

class AllocationAction(BaseModel):
    holder: str
    expected_return_at: Optional[str] = None

class MaintenanceCreate(BaseModel):
    asset_id: str
    description: str
    priority: str = "Medium"
    # --- Detailed work-order fields (optional, non-breaking) ---
    category: str = ""
    location: str = ""
    reporter_contact: str = ""

class MaintenanceStatus(BaseModel):
    status: str

class DepartmentCreate(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    type: str = "academic"
    head: str = Field(default="", max_length=120)

    @field_validator("name", "type", "head")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = (v or "").strip()
        return v

    @field_validator("name")
    @classmethod
    def _non_empty_name(cls, v: str) -> str:
        if len(v) < 2:
            raise ValueError("Department name must be at least 2 non-blank characters")
        return v

class CategoryCreate(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    example_items: str = Field(default="", max_length=300)
    warranty_tracked: bool = False
    amc_tracked: bool = False

    @field_validator("name", "example_items")
    @classmethod
    def _strip(cls, v: str) -> str:
        return (v or "").strip()

    @field_validator("name")
    @classmethod
    def _non_empty_name(cls, v: str) -> str:
        if len(v) < 2:
            raise ValueError("Category name must be at least 2 non-blank characters")
        return v

class RoleChange(BaseModel):
    role: str
    status: str = "Active"

class BookingCreate(BaseModel):
    resource_id: str = Field(min_length=2, max_length=80)
    date: str = Field(min_length=8, max_length=20)
    start_time: str = Field(min_length=4, max_length=8)
    end_time: str = Field(min_length=4, max_length=8)
    purpose: str = Field(min_length=3, max_length=300)
    # --- College-context detail fields (optional, non-breaking) ---
    resource_name: str = Field(default="", max_length=120)
    location: str = Field(default="", max_length=120)
    category: str = Field(default="", max_length=60)
    event_title: str = Field(default="", max_length=120)
    department: str = Field(default="", max_length=80)
    attendees: int = Field(default=0, ge=0, le=100000)
    contact: str = Field(default="", max_length=120)

    @field_validator("resource_id", "date", "start_time", "end_time", "purpose")
    @classmethod
    def _strip_non_empty(cls, v: str, info) -> str:
        v = (v or "").strip()
        if not v:
            raise ValueError(f"{info.field_name} cannot be blank")
        return v

class AuditCreate(BaseModel):
    department: str = Field(min_length=2, max_length=80)
    period: str = Field(min_length=2, max_length=80)
    auditors: List[str] = Field(default_factory=list)

    @field_validator("department", "period")
    @classmethod
    def _strip_non_empty(cls, v: str, info) -> str:
        v = (v or "").strip()
        if len(v) < 2:
            raise ValueError(f"{info.field_name} must be at least 2 non-blank characters")
        return v

class AuditItemUpdate(BaseModel):
    verification: str
    note: str = ""

class NoDuesUpdate(BaseModel):
    status: str
    note: str = ""

class TemplateCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    description: str = Field(default="", max_length=300)
    data_source: str = "assets"
    columns: List[str] = Field(min_length=1)
    filters: dict = Field(default_factory=dict)
    sort_by: str = ""
    sort_order: str = "asc"
    access_roles: List[str] = Field(default_factory=lambda: ["Admin"])

class TemplateUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    data_source: Optional[str] = None
    columns: Optional[List[str]] = None
    filters: Optional[dict] = None
    sort_by: Optional[str] = None
    sort_order: Optional[str] = None
    access_roles: Optional[List[str]] = None
    is_active: Optional[bool] = None

ROLES = {"Admin", "Asset Manager", "HOD", "Employee", "Student"}
ROLE_PERMISSIONS = {
    "Admin": {"admin", "asset_write", "maintenance_write", "booking", "audit", "nodues", "reports"},
    "Asset Manager": {"asset_write", "maintenance_write", "booking", "audit", "reports"},
    "HOD": {"asset_write", "maintenance_write", "booking", "reports"},
    "Employee": {"maintenance_write", "booking", "reports"},
    "Student": {"booking", "maintenance_write"},
}

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def clean(doc):
    if doc is None: return None
    if isinstance(doc, ObjectId): return str(doc)
    if isinstance(doc, list): return [clean(item) for item in doc]
    if isinstance(doc, dict): return {key: clean(value) for key, value in doc.items() if key != "_id"}
    return doc

async def current_user(request: Request):
    token = request.cookies.get("session_token") or request.headers.get("Authorization", "").replace("Bearer ", "")
    if not token: raise HTTPException(401, "Authentication required")
    session = await db.user_sessions.find_one({"session_token": token}, {"_id": 0})
    if not session: raise HTTPException(401, "Session expired")
    expires = session.get("expires_at")
    if isinstance(expires, str): expires = datetime.fromisoformat(expires)
    if expires.tzinfo is None: expires = expires.replace(tzinfo=timezone.utc)
    if expires < datetime.now(timezone.utc): raise HTTPException(401, "Session expired")
    user = await db.users.find_one({"user_id": session["user_id"]}, {"_id": 0})
    if not user: raise HTTPException(401, "User not found")
    # Honor active delegation slot: elevate deputy to Admin during window
    now_ts = datetime.now(timezone.utc).isoformat()
    active = await db.delegations.find_one({"deputy_id": user["user_id"], "status": "Scheduled", "start_at": {"$lte": now_ts}, "end_at": {"$gte": now_ts}}, {"_id": 0})
    if active:
        user["role"] = "Admin"
        user["_delegation_id"] = active["delegation_id"]
        user["_delegated_from"] = active.get("admin_name")
    return user

def require_permission(permission):
    async def checker(user=Depends(current_user)):
        if permission not in ROLE_PERMISSIONS.get(user.get("role"), set()):
            raise HTTPException(403, f"{user.get('role', 'User')} role cannot perform this action")
        return user
    return checker

async def log_event(user, action, entity_type, entity_id, before=None, after=None, metadata=None):
    await db.activity.insert_one({
        "event_id": f"evt_{uuid.uuid4().hex[:12]}", "actor_id": user["user_id"],
        "actor": user.get("name", user["email"]), "action": action,
        "entity_type": entity_type, "entity_id": entity_id, "before": before,
        "after": after, "metadata": metadata or {}, "timestamp": now_iso()
    })

async def create_session(user_id):
    token = secrets.token_urlsafe(32)
    await db.user_sessions.insert_one({"user_id": user_id, "session_token": token, "created_at": now_iso(), "expires_at": (datetime.now(timezone.utc)+timedelta(days=7)).isoformat()})
    return token

def session_response(response, token):
    response.set_cookie("session_token", token, max_age=604800, httponly=True, secure=True, samesite="none", path="/")
    return response

@api.get("/")
async def root(): return {"message": "AssetFlow Campus API"}

@api.post("/auth/signup")
async def signup(payload: Signup, response: Response):
    if await db.users.find_one({"email": payload.email}, {"_id": 0}): raise HTTPException(409, "An account already exists")
    user = {"user_id": f"user_{uuid.uuid4().hex[:12]}", "name": payload.name, "email": payload.email, "role": "Student", "department": "Computer Science", "status": "Pending", "picture": "", "created_at": now_iso()}
    user["password_hash"] = bcrypt.hashpw(payload.password.encode(), bcrypt.gensalt()).decode()
    await db.users.insert_one(user)
    token = await create_session(user["user_id"])
    await log_event(user, "account created", "user", user["user_id"], after={"email": user["email"], "role": user["role"]})
    return session_response(Response(content=__import__("json").dumps(clean({k:v for k,v in user.items() if k != "password_hash"})), media_type="application/json"), token)

@api.post("/auth/login")
async def login(payload: Login):
    user = await db.users.find_one({"email": payload.email}, {"_id": 0})
    if not user or not user.get("password_hash") or not bcrypt.checkpw(payload.password.encode(), user["password_hash"].encode()): raise HTTPException(401, "Invalid email or password")
    token = await create_session(user["user_id"])
    response = Response(content=__import__("json").dumps(clean({k:v for k,v in user.items() if k != "password_hash"})), media_type="application/json")
    return session_response(response, token)

@api.get("/auth/me")
async def me(user=Depends(current_user)): return {k:v for k,v in user.items() if k != "password_hash"}

class ProfileUpdate(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    department: str = Field(default="", max_length=80)
    phone: str = Field(default="", max_length=40)

    @field_validator("name", "department", "phone")
    @classmethod
    def _strip(cls, v: str) -> str: return (v or "").strip()

@api.patch("/auth/profile")
async def update_profile(payload: ProfileUpdate, user=Depends(current_user)):
    if len(payload.name) < 2: raise HTTPException(400, "Name must be at least 2 characters")
    updates = {"name": payload.name, "department": payload.department or user.get("department", ""), "phone": payload.phone}
    await db.users.update_one({"user_id": user["user_id"]}, {"$set": updates})
    await log_event(user, "profile updated", "user", user["user_id"], after=updates)
    fresh = await db.users.find_one({"user_id": user["user_id"]}, {"_id": 0, "password_hash": 0})
    return clean(fresh)

@api.post("/auth/session")
async def oauth_session(request: Request, response: Response):
    try:
        body = await request.json()
        token = body.get("credential")
        if not token: raise HTTPException(400, "Missing Google ID token")
        
        idinfo = id_token.verify_oauth2_token(
            token, 
            google_requests.Request(), 
            os.environ.get("GOOGLE_CLIENT_ID")
        )
        
        if idinfo["iss"] not in ["accounts.google.com", "https://accounts.google.com"]:
            raise HTTPException(401, "Wrong issuer")
            
        if idinfo["email"] and idinfo["email_verified"]:
            user = await db.users.find_one({"email": idinfo["email"]}, {"_id": 0})
            if not user:
                user = {
                    "user_id": f"user_{uuid.uuid4().hex[:12]}", 
                    "name": idinfo.get("name", idinfo["email"].split("@")[0]), 
                    "email": idinfo["email"], 
                    "role": "Student", 
                    "department": "Computer Science", 
                    "status": "Pending", 
                    "picture": idinfo.get("picture", ""), 
                    "created_at": now_iso()
                }
                await db.users.insert_one(user)
                await log_event(user, "account created with Google", "user", user["user_id"], after={"email": user["email"], "role": user["role"]})
            
            session_token = await create_session(user["user_id"])
            return session_response(Response(content=__import__("json").dumps(clean({k:v for k,v in user.items() if k != "password_hash"})), media_type="application/json"), session_token)
        else:
            raise HTTPException(401, "Email not verified")
            
    except Exception as e:
        raise HTTPException(401, f"Invalid Google token: {str(e)}")

@api.post("/auth/logout")
async def logout(request: Request, response: Response):
    token = request.cookies.get("session_token") or request.headers.get("Authorization", "").replace("Bearer ", "")
    if token: await db.user_sessions.delete_one({"session_token": token})
    response.delete_cookie("session_token", path="/")
    return {"ok": True}

@api.get("/dashboard")
async def dashboard(user=Depends(current_user)):
    assets = await db.assets.count_documents({}); available = await db.assets.count_documents({"status":"Available"}); maintenance = await db.maintenance.count_documents({"status":{"$ne":"Resolved"}}); logs = await db.activity.find({}, {"_id":0}).sort("timestamp", -1).to_list(8)
    return {"kpis":{"total_assets":assets,"available":available,"maintenance":maintenance,"utilization":round(((assets-available)/assets*100) if assets else 0)}, "activity":[clean(x) for x in logs], "user":{"name":user["name"],"role":user["role"]}}

@api.get("/assets")
async def assets(search: str = "", status: str = "All", category: str = "All", user=Depends(current_user)):
    query = {}
    if search: query["$or"]=[{"name":{"$regex":search,"$options":"i"}},{"tag":{"$regex":search,"$options":"i"}},{"serial":{"$regex":search,"$options":"i"}}]
    if status != "All": query["status"] = status
    if category != "All": query["category"] = category
    return [clean(x) for x in await db.assets.find(query, {"_id":0}).sort("updated_at", -1).to_list(200)]

@api.post("/assets")
async def create_asset(payload: AssetCreate, user=Depends(current_user)):
    asset={**payload.model_dump(),"asset_id":f"ast_{uuid.uuid4().hex[:10]}","tag":f"AF-{datetime.now().year}-{secrets.randbelow(9000)+1000}","updated_at":now_iso(),"created_at":now_iso()}
    await db.assets.insert_one(asset); await log_event(user,"asset registered","asset",asset["asset_id"],after=asset); return clean(asset)

@api.get("/assets/{asset_id}")
async def asset_detail(asset_id: str, user=Depends(current_user)):
    asset=clean(await db.assets.find_one({"asset_id":asset_id},{"_id":0}))
    if not asset: raise HTTPException(404,"Asset not found")
    events=[clean(x) for x in await db.activity.find({"entity_id":asset_id},{"_id":0}).sort("timestamp",-1).to_list(50)]
    return {"asset":asset,"history":events}

@api.patch("/assets/{asset_id}")
async def update_asset(asset_id: str, payload: AssetUpdate, user=Depends(current_user)):
    before=clean(await db.assets.find_one({"asset_id":asset_id},{"_id":0}))
    if not before: raise HTTPException(404,"Asset not found")
    changes={k:v for k,v in payload.model_dump().items() if v is not None}; changes["updated_at"]=now_iso(); await db.assets.update_one({"asset_id":asset_id},{"$set":changes}); after={**before,**changes}; await log_event(user,"asset updated","asset",asset_id,before=before,after=after); return clean(after)

@api.post("/assets/{asset_id}/checkout")
async def checkout(asset_id: str, payload: AllocationAction, user=Depends(current_user)):
    before=clean(await db.assets.find_one({"asset_id":asset_id},{"_id":0}))
    if not before: raise HTTPException(404,"Asset not found")
    if before["status"] != "Available": raise HTTPException(409,"Asset is not available")
    changes={"status":"Allocated","holder":payload.holder,"expected_return_at":payload.expected_return_at,"updated_at":now_iso()}; await db.assets.update_one({"asset_id":asset_id},{"$set":changes}); after={**before,**changes}; await log_event(user,"asset checked out","asset",asset_id,before=before,after=after); return clean(after)

@api.post("/assets/{asset_id}/checkin")
async def checkin(asset_id: str, user=Depends(current_user)):
    before=clean(await db.assets.find_one({"asset_id":asset_id},{"_id":0}))
    if not before: raise HTTPException(404,"Asset not found")
    changes={"status":"Available","holder":None,"expected_return_at":None,"updated_at":now_iso()}; await db.assets.update_one({"asset_id":asset_id},{"$set":changes}); after={**before,**changes}; await log_event(user,"asset checked in","asset",asset_id,before=before,after=after); return clean(after)

@api.get("/maintenance")
async def maintenance(user=Depends(current_user)):
    cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    purged = await db.maintenance.delete_many({"status": "Resolved", "resolved_at": {"$lt": cutoff}})
    if purged.deleted_count:
        await db.activity.insert_one({"event_id": f"evt_{uuid.uuid4().hex[:12]}","actor_id":"system","actor":"AssetFlow System","action":f"auto-expired {purged.deleted_count} resolved requests (30d)","entity_type":"maintenance","entity_id":"batch","before":None,"after":None,"metadata":{"purged":purged.deleted_count},"timestamp": now_iso()})
    return [clean(x) for x in await db.maintenance.find({}, {"_id":0}).sort("created_at",-1).to_list(200)]

@api.post("/maintenance")
async def create_maintenance(payload: MaintenanceCreate, user=Depends(require_permission("maintenance_write"))):
    item={**payload.model_dump(),"request_id":f"mnt_{uuid.uuid4().hex[:10]}","raised_by":user["name"],"raised_by_id":user["user_id"],"status":"Pending","created_at":now_iso()}; await db.maintenance.insert_one(item); await log_event(user,"maintenance request raised","maintenance",item["request_id"],after=item)
    if payload.priority == "High":
        try: await send_push_to_role(["Admin", "Asset Manager", "HOD"], "High-priority maintenance", f"{item['description'][:80]} · {item['asset_id']}", "/maintenance")
        except Exception as _e: pass
    return clean(item)

@api.patch("/maintenance/{request_id}")
async def update_maintenance(request_id: str, payload: MaintenanceStatus, user=Depends(require_permission("maintenance_write"))):
    before=clean(await db.maintenance.find_one({"request_id":request_id},{"_id":0}))
    if not before: raise HTTPException(404,"Request not found")
    if payload.status not in {"Pending","Approved","In progress","Resolved","Rejected"}: raise HTTPException(400,"Invalid status")
    changes = {"status": payload.status}
    if payload.status == "Resolved": changes["resolved_at"] = now_iso()
    if payload.status == "Rejected": changes["rejected_at"] = now_iso()
    await db.maintenance.update_one({"request_id":request_id},{"$set":changes})
    after={**before,**changes}; await log_event(user,"maintenance status changed","maintenance",request_id,before=before,after=after); return clean(after)

@api.delete("/maintenance/{request_id}")
async def delete_maintenance(request_id: str, user=Depends(require_permission("maintenance_write"))):
    before=clean(await db.maintenance.find_one({"request_id":request_id},{"_id":0}))
    if not before: raise HTTPException(404,"Request not found")
    if user.get("role") not in {"Admin","Asset Manager","HOD"} and before.get("raised_by_id") != user.get("user_id"):
        raise HTTPException(403,"Cannot delete another user's request")
    await db.maintenance.delete_one({"request_id":request_id})
    await log_event(user,"maintenance request removed","maintenance",request_id,before=before); return {"ok": True}

@api.get("/activity")
async def activity(user=Depends(current_user)): return [clean(x) for x in await db.activity.find({}, {"_id":0}).sort("timestamp",-1).to_list(200)]

@api.get("/reports")
async def reports(user=Depends(require_permission("reports"))):
    assets=[clean(x) for x in await db.assets.find({}, {"_id":0}).to_list(500)]; by_dept={}
    for a in assets: by_dept.setdefault(a["department"],{"name":a["department"],"total":0,"allocated":0}); by_dept[a["department"]]["total"]+=1; by_dept[a["department"]]["allocated"]+=a["status"]=="Allocated"
    return {"departments":list(by_dept.values()),"status_counts":{s:sum(a["status"]==s for a in assets) for s in ["Available","Allocated","Under Maintenance","Lost","Retired"]},"total":len(assets)}

@api.get("/admin/departments")
async def get_departments(user=Depends(require_permission("admin"))):
    return [clean(x) for x in await db.departments.find({}, {"_id": 0}).sort("name", 1).to_list(100)]

@api.post("/admin/departments")
async def create_department(payload: DepartmentCreate, user=Depends(require_permission("admin"))):
    item = {**payload.model_dump(), "department_id": f"dept_{uuid.uuid4().hex[:10]}", "status": "Active", "created_at": now_iso()}
    await db.departments.insert_one(item); await log_event(user, "department created", "department", item["department_id"], after=item); return clean(item)

@api.get("/admin/categories")
async def get_categories(user=Depends(require_permission("admin"))):
    return [clean(x) for x in await db.categories.find({}, {"_id": 0}).sort("name", 1).to_list(100)]

@api.post("/admin/categories")
async def create_category(payload: CategoryCreate, user=Depends(require_permission("admin"))):
    item = {**payload.model_dump(), "category_id": f"cat_{uuid.uuid4().hex[:10]}", "created_at": now_iso()}
    await db.categories.insert_one(item); await log_event(user, "category created", "category", item["category_id"], after=item); return clean(item)

@api.get("/admin/users")
async def get_admin_users(user=Depends(require_permission("admin"))):
    return [{k: v for k, v in clean(x).items() if k != "password_hash"} for x in await db.users.find({}, {"_id": 0}).sort("created_at", -1).to_list(200)]

@api.patch("/admin/users/{user_id}/role")
async def change_role(user_id: str, payload: RoleChange, user=Depends(require_permission("admin"))):
    if payload.role not in ROLES: raise HTTPException(400, "Unknown role")
    before = clean(await db.users.find_one({"user_id": user_id}, {"_id": 0}))
    if not before: raise HTTPException(404, "User not found")
    if user_id == user["user_id"] and payload.role != "Admin": raise HTTPException(400, "Admins cannot remove their own admin access")
    await db.users.update_one({"user_id": user_id}, {"$set": {"role": payload.role, "status": payload.status}})
    await db.user_sessions.delete_many({"user_id": user_id})
    after = {**before, "role": payload.role, "status": payload.status}
    await log_event(user, "role approval changed", "user", user_id, before={"role": before.get("role"), "status": before.get("status")}, after={"role": payload.role, "status": payload.status})
    return {k: v for k, v in clean(after).items() if k != "password_hash"}

class BulkRoleChange(BaseModel):
    user_ids: List[str] = Field(min_length=1)
    role: str
    status: str = "Active"

@api.post("/admin/users/bulk-role")
async def bulk_change_role(payload: BulkRoleChange, user=Depends(require_permission("admin"))):
    if payload.role not in ROLES: raise HTTPException(400, "Unknown role")
    updated, skipped = [], []
    for uid in payload.user_ids:
        target = await db.users.find_one({"user_id": uid}, {"_id": 0})
        if not target: skipped.append({"user_id": uid, "reason": "not found"}); continue
        if uid == user["user_id"] and payload.role != "Admin": skipped.append({"user_id": uid, "reason": "cannot remove own admin access"}); continue
        if target.get("email") == "admin@assetflow.edu" and payload.role != "Admin": skipped.append({"user_id": uid, "reason": "root admin protected"}); continue
        await db.users.update_one({"user_id": uid}, {"$set": {"role": payload.role, "status": payload.status}})
        await db.user_sessions.delete_many({"user_id": uid})
        updated.append(uid)
    await log_event(user, f"bulk role change to {payload.role}", "user", "batch", after={"count": len(updated), "role": payload.role, "status": payload.status})
    return {"updated": len(updated), "skipped": skipped, "role": payload.role, "status": payload.status}

@api.get("/search")
async def global_search(q: str = "", user=Depends(current_user)):
    q = (q or "").strip()
    empty = {"assets": [], "users": [], "bookings": [], "maintenance": []}
    if len(q) < 1: return empty
    rx = {"$regex": q, "$options": "i"}
    assets = await db.assets.find({"$or": [{"name": rx}, {"tag": rx}, {"serial": rx}, {"location": rx}, {"category": rx}]}, {"_id": 0}).limit(6).to_list(6)
    maints = await db.maintenance.find({"$or": [{"description": rx}, {"asset_id": rx}, {"priority": rx}, {"status": rx}]}, {"_id": 0}).limit(6).to_list(6)
    bookings = await db.bookings.find({"$or": [{"resource_name": rx}, {"event_title": rx}, {"purpose": rx}, {"requested_by": rx}]}, {"_id": 0}).limit(6).to_list(6)
    users_out = []
    if user.get("role") == "Admin":
        us = await db.users.find({"$or": [{"name": rx}, {"email": rx}, {"department": rx}, {"role": rx}]}, {"_id": 0, "password_hash": 0}).limit(6).to_list(6)
        users_out = [clean(u) for u in us]
    return {"assets": [clean(a) for a in assets], "maintenance": [clean(m) for m in maints], "bookings": [clean(b) for b in bookings], "users": users_out}

@api.get("/bookings")
async def get_bookings(date: str = "", user=Depends(current_user)):
    query = {"date": date} if date else {}
    return [clean(x) for x in await db.bookings.find(query, {"_id": 0}).sort([("date", 1), ("start_time", 1)]).to_list(200)]

@api.post("/bookings")
async def create_booking(payload: BookingCreate, user=Depends(require_permission("booking"))):
    conflict = await db.bookings.find_one({"resource_id": payload.resource_id, "date": payload.date, "status": "Confirmed", "start_time": {"$lt": payload.end_time}, "end_time": {"$gt": payload.start_time}}, {"_id": 0})
    if conflict: raise HTTPException(409, "This resource is already booked for that time")
    item = {**payload.model_dump(), "booking_id": f"book_{uuid.uuid4().hex[:10]}", "requested_by": user["name"], "requested_by_id": user["user_id"], "status": "Confirmed", "created_at": now_iso()}
    await db.bookings.insert_one(item); await log_event(user, "booking created", "booking", item["booking_id"], after=item); return clean(item)

@api.delete("/bookings/{booking_id}")
async def delete_booking(booking_id: str, user=Depends(require_permission("booking"))):
    before = clean(await db.bookings.find_one({"booking_id": booking_id}, {"_id": 0}))
    if not before: raise HTTPException(404, "Booking not found")
    if before.get("requested_by_id") != user["user_id"] and user["role"] not in {"Admin", "Asset Manager", "HOD"}: raise HTTPException(403, "Cannot cancel another user's booking")
    await db.bookings.delete_one({"booking_id": booking_id}); await log_event(user, "booking cancelled", "booking", booking_id, before=before); return {"ok": True}

@api.get("/audits")
async def get_audits(user=Depends(require_permission("audit"))):
    return [clean(x) for x in await db.audits.find({}, {"_id": 0}).sort("created_at", -1).to_list(100)]

@api.post("/audits")
async def create_audit(payload: AuditCreate, user=Depends(require_permission("audit"))):
    assets = [clean(x) for x in await db.assets.find({"department": payload.department}, {"_id": 0}).to_list(500)]
    item = {**payload.model_dump(), "audit_id": f"audit_{uuid.uuid4().hex[:10]}", "status": "Open", "created_at": now_iso(), "items": [{"asset_id": x["asset_id"], "tag": x["tag"], "name": x["name"], "expected_location": x["location"], "verification": "Pending", "note": ""} for x in assets]}
    await db.audits.insert_one(item); await log_event(user, "audit cycle opened", "audit", item["audit_id"], after=item); return clean(item)

@api.patch("/audits/{audit_id}/items/{asset_id}")
async def update_audit_item(audit_id: str, asset_id: str, payload: AuditItemUpdate, user=Depends(require_permission("audit"))):
    if payload.verification not in {"Verified", "Missing", "Damaged"}: raise HTTPException(400, "Invalid verification")
    before = clean(await db.audits.find_one({"audit_id": audit_id}, {"_id": 0}))
    if not before: raise HTTPException(404, "Audit cycle not found")
    await db.audits.update_one({"audit_id": audit_id, "items.asset_id": asset_id}, {"$set": {"items.$.verification": payload.verification, "items.$.note": payload.note}})
    after = {**before, "items": [{**x, "verification": payload.verification, "note": payload.note} if x["asset_id"] == asset_id else x for x in before["items"]]}
    await log_event(user, "audit item verified", "audit", audit_id, before=before, after=after); return clean(after)

@api.post("/audits/{audit_id}/close")
async def close_audit(audit_id: str, user=Depends(require_permission("audit"))):
    before = clean(await db.audits.find_one({"audit_id": audit_id}, {"_id": 0}))
    if not before: raise HTTPException(404, "Audit cycle not found")
    await db.audits.update_one({"audit_id": audit_id}, {"$set": {"status": "Closed", "closed_at": now_iso()}})
    after = {**before, "status": "Closed", "closed_at": now_iso()}; await log_event(user, "audit cycle closed", "audit", audit_id, before=before, after=after); return clean(after)

@api.get("/nodues")
async def get_nodues(user=Depends(require_permission("nodues"))):
    return [clean(x) for x in await db.nodues.find({}, {"_id": 0}).sort("student_name", 1).to_list(200)]

@api.patch("/nodues/{student_id}/{department}")
async def update_nodues(student_id: str, department: str, payload: NoDuesUpdate, user=Depends(require_permission("nodues"))):
    before = clean(await db.nodues.find_one({"student_id": student_id}, {"_id": 0}))
    if not before: raise HTTPException(404, "No-dues record not found")
    statuses = [{**x, "status": payload.status, "note": payload.note} if x["department"] == department else x for x in before["department_statuses"]]
    overall = "Cleared" if all(x["status"] == "Cleared" for x in statuses) else "In progress"
    await db.nodues.update_one({"student_id": student_id}, {"$set": {"department_statuses": statuses, "overall_status": overall}})
    after = {**before, "department_statuses": statuses, "overall_status": overall}; await log_event(user, "no-dues status updated", "nodues", student_id, before=before, after=after); return clean(after)

@api.get("/reports/accreditation")
async def accreditation_report(user=Depends(require_permission("reports"))):
    assets = await db.assets.count_documents({}); events = await db.activity.count_documents({}); audits = await db.audits.count_documents({"status": "Closed"}); maintenance = await db.maintenance.count_documents({})
    return {"title": "AssetFlow Campus Accreditation Evidence", "generated_at": now_iso(), "metrics": {"tracked_assets": assets, "audited_cycles": audits, "maintenance_records": maintenance, "activity_events": events}, "format": "NAAC/NBA-ready"}

@api.get("/reports/accreditation/download")
async def accreditation_download(format: str = "csv", user=Depends(require_permission("reports"))):
    from fastapi.responses import StreamingResponse
    import io, csv
    assets_total = await db.assets.count_documents({})
    assets_by_status = {}
    for s in ["Available", "Allocated", "Under Maintenance", "Lost", "Retired"]:
        assets_by_status[s] = await db.assets.count_documents({"status": s})
    audits_total = await db.audits.count_documents({})
    audits_closed = await db.audits.count_documents({"status": "Closed"})
    maint_total = await db.maintenance.count_documents({})
    maint_resolved = await db.maintenance.count_documents({"status": "Resolved"})
    bookings_total = await db.bookings.count_documents({})
    events = await db.activity.count_documents({})
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    rows = [
        ("Metric", "Value"),
        ("Report title", "AssetFlow Campus Accreditation Evidence"),
        ("Generated at (UTC)", generated),
        ("Prepared by", user.get("name", "")),
        ("Format target", "NAAC / NBA"),
        ("", ""),
        ("Total tracked assets", assets_total),
        *[(f"Assets — {k}", v) for k, v in assets_by_status.items()],
        ("", ""),
        ("Audit cycles — total", audits_total),
        ("Audit cycles — closed", audits_closed),
        ("Maintenance records — total", maint_total),
        ("Maintenance records — resolved", maint_resolved),
        ("Bookings — total", bookings_total),
        ("Activity events logged", events),
    ]
    if format == "csv":
        buf = io.StringIO(); writer = csv.writer(buf)
        for row in rows: writer.writerow(row)
        buf.seek(0)
        await log_event(user, "accreditation report downloaded", "report", "accreditation", metadata={"format": "csv"})
        return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="assetflow_accreditation.csv"'})
    if format == "pdf":
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, PageBreak
        import urllib.request, tempfile
        brand = {**BRANDING_DEFAULT, **{k: v for k, v in ((await db.branding.find_one({"_id": "singleton"})) or {}).items() if k != "_id"}}
        try: accent = colors.HexColor(brand.get("accent_color") or "#171717")
        except Exception: accent = colors.HexColor("#171717")
        buf = io.BytesIO(); doc = SimpleDocTemplate(buf, pagesize=A4, title=f"{brand['institution_name']} · Accreditation")
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle("cover_title", parent=styles["Title"], textColor=accent, fontSize=30, leading=34, spaceAfter=8)
        eyebrow_style = ParagraphStyle("cover_eyebrow", parent=styles["Normal"], textColor=colors.HexColor("#8f8f8f"), fontSize=10, spaceAfter=6)
        subtitle_style = ParagraphStyle("cover_subtitle", parent=styles["Heading2"], textColor=colors.HexColor("#171717"), fontSize=16, leading=20, spaceAfter=20)
        story = []
        logo_url = brand.get("logo_url") or ""
        if logo_url.startswith("https://"):
            try:
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".img")
                with urllib.request.urlopen(logo_url, timeout=5) as r: tmp.write(r.read())
                tmp.close()
                story.append(Image(tmp.name, width=42*mm, height=42*mm, kind="proportional"))
                story.append(Spacer(1, 12))
            except Exception as _e: pass
        story.append(Paragraph(brand.get("accreditation_body") or "NAAC / NBA", eyebrow_style))
        story.append(Paragraph(brand.get("institution_name") or "AssetFlow Campus", title_style))
        if brand.get("tagline"): story.append(Paragraph(brand["tagline"], subtitle_style))
        story.append(Spacer(1, 30))
        story.append(Paragraph("Accreditation Evidence Report", styles["Heading2"]))
        story.append(Paragraph(f"Generated {generated} · Prepared by {user.get('name','')}", styles["Normal"]))
        story.append(PageBreak())
        story.append(Paragraph("Metrics summary", styles["Heading2"]))
        story.append(Spacer(1, 12))
        data = [[str(a), str(b)] for a, b in rows if a or b]
        table = Table(data, colWidths=[280, 200])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), accent),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#ebebeb")),
        ]))
        story.append(table)
        story.append(Spacer(1, 24))
        footer_text = brand.get("footer") or BRANDING_DEFAULT["footer"]
        story.append(Paragraph(footer_text, styles["Italic"]))
        doc.build(story); buf.seek(0)
        await log_event(user, "accreditation report downloaded", "report", "accreditation", metadata={"format": "pdf"})
        return StreamingResponse(iter([buf.getvalue()]), media_type="application/pdf", headers={"Content-Disposition": 'attachment; filename="assetflow_accreditation.pdf"'})
    raise HTTPException(400, "Unsupported format. Use csv or pdf.")

# ============================================================
# Advanced Reports Download System & Admin Report Builder
# ============================================================

DATA_SOURCES_SCHEMA = {
    "assets": {
        "label": "Assets & Equipment",
        "collection": "assets",
        "columns": [
            {"key": "tag", "label": "Asset Tag", "type": "string"},
            {"key": "name", "label": "Asset Name", "type": "string"},
            {"key": "category", "label": "Category", "type": "string"},
            {"key": "department", "label": "Department", "type": "string"},
            {"key": "location", "label": "Location", "type": "string"},
            {"key": "status", "label": "Status", "type": "string"},
            {"key": "holder", "label": "Current Holder", "type": "string"},
            {"key": "serial", "label": "Serial Number", "type": "string"},
            {"key": "bookable", "label": "Bookable", "type": "boolean"},
            {"key": "purchase_cost", "label": "Purchase Cost", "type": "number"},
            {"key": "purchase_date", "label": "Purchase Date", "type": "date"},
            {"key": "warranty_end", "label": "Warranty End", "type": "date"},
            {"key": "supplier", "label": "Supplier", "type": "string"},
            {"key": "created_at", "label": "Registered Date", "type": "datetime"},
        ],
        "filterable_fields": [
            {"key": "department", "label": "Department"},
            {"key": "status", "label": "Status"},
            {"key": "category", "label": "Category"},
            {"key": "bookable", "label": "Bookable"},
        ]
    },
    "maintenance": {
        "label": "Maintenance & Work Orders",
        "collection": "maintenance",
        "columns": [
            {"key": "request_id", "label": "Request ID", "type": "string"},
            {"key": "asset_id", "label": "Asset ID", "type": "string"},
            {"key": "description", "label": "Description", "type": "string"},
            {"key": "priority", "label": "Priority", "type": "string"},
            {"key": "status", "label": "Status", "type": "string"},
            {"key": "raised_by", "label": "Raised By", "type": "string"},
            {"key": "created_at", "label": "Date Raised", "type": "datetime"},
            {"key": "resolved_at", "label": "Date Resolved", "type": "datetime"}
        ],
        "filterable_fields": [
            {"key": "priority", "label": "Priority"},
            {"key": "status", "label": "Status"}
        ]
    },
    "bookings": {
        "label": "Resource Bookings",
        "collection": "bookings",
        "columns": [
            {"key": "booking_id", "label": "Booking ID", "type": "string"},
            {"key": "resource_name", "label": "Resource / Room", "type": "string"},
            {"key": "department", "label": "Department", "type": "string"},
            {"key": "date", "label": "Date", "type": "date"},
            {"key": "start_time", "label": "Start Time", "type": "string"},
            {"key": "end_time", "label": "End Time", "type": "string"},
            {"key": "event_title", "label": "Event Title", "type": "string"},
            {"key": "purpose", "label": "Purpose", "type": "string"},
            {"key": "requested_by", "label": "Requested By", "type": "string"},
            {"key": "attendees", "label": "Attendees", "type": "number"},
            {"key": "status", "label": "Status", "type": "string"}
        ],
        "filterable_fields": [
            {"key": "department", "label": "Department"},
            {"key": "status", "label": "Status"}
        ]
    },
    "users": {
        "label": "Users & Staff Roster",
        "collection": "users",
        "columns": [
            {"key": "user_id", "label": "User ID", "type": "string"},
            {"key": "name", "label": "Full Name", "type": "string"},
            {"key": "email", "label": "Email", "type": "string"},
            {"key": "role", "label": "Role", "type": "string"},
            {"key": "department", "label": "Department", "type": "string"},
            {"key": "status", "label": "Status", "type": "string"},
            {"key": "phone", "label": "Phone", "type": "string"},
            {"key": "created_at", "label": "Joined Date", "type": "datetime"}
        ],
        "filterable_fields": [
            {"key": "role", "label": "Role"},
            {"key": "department", "label": "Department"},
            {"key": "status", "label": "Status"}
        ]
    },
    "activity": {
        "label": "Activity & Audit Events",
        "collection": "activity",
        "columns": [
            {"key": "event_id", "label": "Event ID", "type": "string"},
            {"key": "actor", "label": "Actor", "type": "string"},
            {"key": "action", "label": "Action", "type": "string"},
            {"key": "entity_type", "label": "Entity Type", "type": "string"},
            {"key": "entity_id", "label": "Entity ID", "type": "string"},
            {"key": "timestamp", "label": "Timestamp", "type": "datetime"}
        ],
        "filterable_fields": [
            {"key": "entity_type", "label": "Entity Type"}
        ]
    },
    "audits": {
        "label": "Audit Cycles",
        "collection": "audits",
        "columns": [
            {"key": "audit_id", "label": "Audit ID", "type": "string"},
            {"key": "department", "label": "Department", "type": "string"},
            {"key": "period", "label": "Period", "type": "string"},
            {"key": "status", "label": "Status", "type": "string"},
            {"key": "created_at", "label": "Created At", "type": "datetime"},
            {"key": "closed_at", "label": "Closed At", "type": "datetime"}
        ],
        "filterable_fields": [
            {"key": "department", "label": "Department"},
            {"key": "status", "label": "Status"}
        ]
    },
    "nodues": {
        "label": "No-Dues Clearance",
        "collection": "nodues",
        "columns": [
            {"key": "student_id", "label": "Student ID", "type": "string"},
            {"key": "student_name", "label": "Student Name", "type": "string"},
            {"key": "roll_number", "label": "Roll Number", "type": "string"},
            {"key": "overall_status", "label": "Overall Status", "type": "string"}
        ],
        "filterable_fields": [
            {"key": "overall_status", "label": "Overall Status"}
        ]
    }
}

async def get_active_brand():
    raw = (await db.branding.find_one({"_id": "singleton"})) or {}
    return {**BRANDING_DEFAULT, **{k: v for k, v in raw.items() if k != "_id"}}

def build_report_csv(headers: list, rows: list) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    if headers:
        writer.writerow(headers)
    for r in rows:
        writer.writerow([str(c if c is not None else "") for c in r])
    buf.seek(0)
    return buf.getvalue()

def build_generic_report_pdf(title: str, subtitle: str, meta_pairs: list, headers: list, rows: list, brand: dict, footer_text: Optional[str] = None, col_widths: Optional[list] = None) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
    import urllib.request, tempfile

    try: accent = colors.HexColor(brand.get("accent_color") or "#171717")
    except Exception: accent = colors.HexColor("#171717")

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=28, rightMargin=28, topMargin=28, bottomMargin=28, title=title)
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle("rep_title", parent=styles["Title"], textColor=accent, fontSize=18, leading=22, spaceAfter=3, alignment=0)
    eyebrow_style = ParagraphStyle("rep_eyebrow", parent=styles["Normal"], textColor=colors.HexColor("#8f8f8f"), fontSize=8.5, leading=10, spaceAfter=3)
    sub_style = ParagraphStyle("rep_sub", parent=styles["Normal"], textColor=colors.HexColor("#4d4d4d"), fontSize=10, leading=13, spaceAfter=12)
    meta_k = ParagraphStyle("rep_mk", parent=styles["Normal"], textColor=colors.HexColor("#737373"), fontSize=7.5, leading=9.5, fontName="Helvetica-Bold")
    meta_v = ParagraphStyle("rep_mv", parent=styles["Normal"], textColor=colors.HexColor("#171717"), fontSize=8, leading=10)
    hdr_style = ParagraphStyle("rep_th", parent=styles["Normal"], textColor=colors.white, fontSize=7.5, leading=9, fontName="Helvetica-Bold")
    cell_style = ParagraphStyle("rep_td", parent=styles["Normal"], textColor=colors.HexColor("#171717"), fontSize=7.2, leading=8.8)

    story = []

    logo_url = brand.get("logo_url") or ""
    if logo_url.startswith("https://"):
        try:
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".img")
            with urllib.request.urlopen(logo_url, timeout=3) as r: tmp.write(r.read())
            tmp.close()
            story.append(Image(tmp.name, width=24*mm, height=24*mm, kind="proportional"))
            story.append(Spacer(1, 4))
        except Exception: pass

    eyebrow_text = f"{brand.get('institution_name', 'AssetFlow Campus')} · {brand.get('accreditation_body', 'Report Center')}".upper()
    story.append(Paragraph(eyebrow_text, eyebrow_style))
    story.append(Paragraph(title, title_style))
    if subtitle:
        story.append(Paragraph(subtitle, sub_style))

    if meta_pairs:
        meta_table_rows = []
        for i in range(0, len(meta_pairs), 2):
            k1, v1 = meta_pairs[i]
            k2, v2 = meta_pairs[i+1] if i+1 < len(meta_pairs) else ("", "")
            meta_table_rows.append([
                Paragraph(k1, meta_k) if k1 else "",
                Paragraph(str(v1), meta_v) if k1 else "",
                Paragraph(k2, meta_k) if k2 else "",
                Paragraph(str(v2), meta_v) if k2 else "",
            ])
        meta_tbl = Table(meta_table_rows, colWidths=[90, 178, 90, 178])
        meta_tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8f8f8")),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#e5e5e5")),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        story.append(meta_tbl)
        story.append(Spacer(1, 10))

    avail_w = 595 - 56
    num_cols = max(1, len(headers))
    if not col_widths or len(col_widths) != num_cols:
        col_widths = [avail_w / num_cols] * num_cols
    else:
        tot = sum(col_widths)
        if tot > 0:
            scale = avail_w / tot
            col_widths = [w * scale for w in col_widths]

    def esc(text):
        s = str(text if text is not None else "—")
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    tbl_data = [[Paragraph(esc(h), hdr_style) for h in headers]]
    if rows:
        for r in rows:
            tbl_data.append([Paragraph(esc(c), cell_style) for c in r])
    else:
        empty_row = [Paragraph("No records found matching criteria", cell_style)] + [Paragraph("", cell_style) for _ in range(num_cols - 1)]
        tbl_data.append(empty_row)

    data_tbl = Table(tbl_data, colWidths=col_widths, repeatRows=1)
    t_styles = [
        ("BACKGROUND", (0, 0), (-1, 0), accent),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#e5e5e5")),
    ]
    for idx in range(1, len(tbl_data)):
        bg = colors.white if idx % 2 == 1 else colors.HexColor("#fafafa")
        t_styles.append(("BACKGROUND", (0, idx), (-1, idx), bg))

    data_tbl.setStyle(TableStyle(t_styles))
    story.append(data_tbl)

    story.append(Spacer(1, 14))
    f_text = footer_text or brand.get("footer") or BRANDING_DEFAULT["footer"]
    story.append(Paragraph(f_text, ParagraphStyle("rep_ft", parent=styles["Italic"], textColor=colors.HexColor("#737373"), fontSize=7.5, leading=9.5)))

    doc.build(story)
    buf.seek(0)
    return buf.getvalue()

def build_single_asset_pdf(asset: dict, events: list, maints: list, bks: list, auds: list, brand: dict, prepared_by: str) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
    import urllib.request, tempfile

    try: accent = colors.HexColor(brand.get("accent_color") or "#171717")
    except Exception: accent = colors.HexColor("#171717")

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=28, rightMargin=28, topMargin=28, bottomMargin=28, title=f"Lifecycle {asset.get('tag', '')}")
    styles = getSampleStyleSheet()

    title_s = ParagraphStyle("ast_t", parent=styles["Title"], textColor=accent, fontSize=18, leading=22, spaceAfter=2, alignment=0)
    eye_s = ParagraphStyle("ast_eye", parent=styles["Normal"], textColor=colors.HexColor("#8f8f8f"), fontSize=8.5, leading=10, spaceAfter=4)
    sec_s = ParagraphStyle("ast_sec", parent=styles["Heading2"], textColor=accent, fontSize=11, leading=14, spaceBefore=8, spaceAfter=4)
    mk_s = ParagraphStyle("ast_mk", parent=styles["Normal"], textColor=colors.HexColor("#666666"), fontSize=7.5, leading=9.5, fontName="Helvetica-Bold")
    mv_s = ParagraphStyle("ast_mv", parent=styles["Normal"], textColor=colors.HexColor("#171717"), fontSize=8, leading=10)
    th_s = ParagraphStyle("ast_th", parent=styles["Normal"], textColor=colors.white, fontSize=7.5, leading=9, fontName="Helvetica-Bold")
    td_s = ParagraphStyle("ast_td", parent=styles["Normal"], textColor=colors.HexColor("#171717"), fontSize=7.2, leading=8.8)

    def esc(text):
        s = str(text if text is not None else "—")
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    story = []

    logo_url = brand.get("logo_url") or ""
    if logo_url.startswith("https://"):
        try:
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".img")
            with urllib.request.urlopen(logo_url, timeout=3) as r: tmp.write(r.read())
            tmp.close()
            story.append(Image(tmp.name, width=22*mm, height=22*mm, kind="proportional"))
            story.append(Spacer(1, 4))
        except Exception: pass

    story.append(Paragraph(f"{brand.get('institution_name', 'AssetFlow Campus')} · SINGLE ASSET LIFECYCLE AUDIT REPORT".upper(), eye_s))
    story.append(Paragraph(f"{asset.get('name', 'Asset')} ({asset.get('tag', '')})", title_s))
    story.append(Paragraph(f"Comprehensive lifecycle trace, maintenance logs, booking load, and audit verification history.", eye_s))
    story.append(Spacer(1, 6))

    # Asset profile card (2x5 grid)
    spec_rows = [
        [Paragraph("Asset Tag", mk_s), Paragraph(esc(asset.get("tag")), mv_s), Paragraph("Department", mk_s), Paragraph(esc(asset.get("department")), mv_s)],
        [Paragraph("Category", mk_s), Paragraph(esc(asset.get("category")), mv_s), Paragraph("Location", mk_s), Paragraph(esc(asset.get("location")), mv_s)],
        [Paragraph("Status", mk_s), Paragraph(esc(asset.get("status")), mv_s), Paragraph("Current Holder", mk_s), Paragraph(esc(asset.get("holder")), mv_s)],
        [Paragraph("Serial No.", mk_s), Paragraph(esc(asset.get("serial")), mv_s), Paragraph("Bookable", mk_s), Paragraph("Yes" if asset.get("bookable") else "No", mv_s)],
        [Paragraph("Purchase Cost", mk_s), Paragraph(f"Rs. {asset.get('purchase_cost', 0):,.2f}" if asset.get("purchase_cost") else "—", mv_s), Paragraph("Purchase Date", mk_s), Paragraph(esc(asset.get("purchase_date")), mv_s)],
        [Paragraph("Supplier", mk_s), Paragraph(esc(asset.get("supplier")), mv_s), Paragraph("Warranty End", mk_s), Paragraph(esc(asset.get("warranty_end")), mv_s)],
        [Paragraph("Report Date", mk_s), Paragraph(datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), mv_s), Paragraph("Prepared By", mk_s), Paragraph(esc(prepared_by), mv_s)],
    ]
    spec_tbl = Table(spec_rows, colWidths=[90, 178, 90, 178])
    spec_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8f8f8")),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#e5e5e5")),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(spec_tbl)

    # Section 1: Allocation & Lifecycle Timeline
    story.append(Paragraph("1. Allocation & Lifecycle Timeline (Activity Trail)", sec_s))
    evt_headers = ["Timestamp (UTC)", "Actor", "Action", "Details"]
    evt_rows = []
    for ev in events:
        ts = ev.get("timestamp", "")[:19].replace("T", " ")
        meta_str = ", ".join(f"{k}: {v}" for k, v in (ev.get("metadata") or {}).items()) if ev.get("metadata") else "—"
        evt_rows.append([ts, ev.get("actor", "System"), ev.get("action", ""), meta_str])
    
    evt_table_data = [[Paragraph(esc(h), th_s) for h in evt_headers]]
    if evt_rows:
        for r in evt_rows:
            evt_table_data.append([Paragraph(esc(c), td_s) for c in r])
    else:
        evt_table_data.append([Paragraph("No lifecycle events recorded", td_s)] + [Paragraph("", td_s) for _ in range(3)])

    evt_tbl = Table(evt_table_data, colWidths=[95, 95, 130, 216], repeatRows=1)
    evt_styles = [
        ("BACKGROUND", (0, 0), (-1, 0), accent),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#e5e5e5")),
    ]
    for idx in range(1, len(evt_table_data)):
        evt_styles.append(("BACKGROUND", (0, idx), (-1, idx), colors.white if idx % 2 == 1 else colors.HexColor("#fafafa")))
    evt_tbl.setStyle(TableStyle(evt_styles))
    story.append(evt_tbl)

    # Section 2: Maintenance History
    story.append(Paragraph("2. Maintenance & Work Order History", sec_s))
    m_headers = ["Request ID", "Priority", "Status", "Description", "Raised By", "Created", "Resolved"]
    m_rows = []
    for m in maints:
        m_rows.append([
            m.get("request_id", ""),
            m.get("priority", "Medium"),
            m.get("status", ""),
            m.get("description", ""),
            m.get("raised_by", ""),
            m.get("created_at", "")[:10],
            (m.get("resolved_at") or "—")[:10]
        ])
    m_table_data = [[Paragraph(esc(h), th_s) for h in m_headers]]
    if m_rows:
        for r in m_rows:
            m_table_data.append([Paragraph(esc(c), td_s) for c in r])
    else:
        m_table_data.append([Paragraph("No maintenance requests recorded for this asset", td_s)] + [Paragraph("", td_s) for _ in range(6)])
    m_tbl = Table(m_table_data, colWidths=[65, 45, 60, 166, 75, 60, 65], repeatRows=1)
    m_styles = [
        ("BACKGROUND", (0, 0), (-1, 0), accent),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#e5e5e5")),
    ]
    for idx in range(1, len(m_table_data)):
        m_styles.append(("BACKGROUND", (0, idx), (-1, idx), colors.white if idx % 2 == 1 else colors.HexColor("#fafafa")))
    m_tbl.setStyle(TableStyle(m_styles))
    story.append(m_tbl)

    # Section 3: Booking Log (if bookable or bookings exist)
    if bks or asset.get("bookable"):
        story.append(Paragraph("3. Room / Equipment Reservation Log", sec_s))
        b_headers = ["Booking ID", "Date", "Slot", "Event / Purpose", "Requested By", "Status"]
        b_rows = []
        for b in bks:
            b_rows.append([
                b.get("booking_id", ""),
                b.get("date", ""),
                f"{b.get('start_time','')} - {b.get('end_time','')}",
                b.get("event_title") or b.get("purpose", ""),
                b.get("requested_by", ""),
                b.get("status", "")
            ])
        b_table_data = [[Paragraph(esc(h), th_s) for h in b_headers]]
        if b_rows:
            for r in b_rows:
                b_table_data.append([Paragraph(esc(c), td_s) for c in r])
        else:
            b_table_data.append([Paragraph("No bookings recorded", td_s)] + [Paragraph("", td_s) for _ in range(5)])
        b_tbl = Table(b_table_data, colWidths=[70, 65, 80, 160, 95, 66], repeatRows=1)
        b_styles = [
            ("BACKGROUND", (0, 0), (-1, 0), accent),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#e5e5e5")),
        ]
        for idx in range(1, len(b_table_data)):
            b_styles.append(("BACKGROUND", (0, idx), (-1, idx), colors.white if idx % 2 == 1 else colors.HexColor("#fafafa")))
        b_tbl.setStyle(TableStyle(b_styles))
        story.append(b_tbl)

    # Section 4: Audit Verifications
    story.append(Paragraph("4. Physical Audit Verification History", sec_s))
    a_headers = ["Audit ID", "Department", "Period", "Verification", "Auditor Notes", "Status"]
    a_rows = []
    for a in auds:
        for it in a.get("items", []):
            if it.get("asset_id") == asset.get("asset_id") or it.get("tag") == asset.get("tag"):
                a_rows.append([
                    a.get("audit_id", ""),
                    a.get("department", ""),
                    a.get("period", ""),
                    it.get("verification", "Pending"),
                    it.get("note", "—"),
                    a.get("status", "")
                ])
    a_table_data = [[Paragraph(esc(h), th_s) for h in a_headers]]
    if a_rows:
        for r in a_rows:
            a_table_data.append([Paragraph(esc(c), td_s) for c in r])
    else:
        a_table_data.append([Paragraph("No physical audit cycle verifications logged", td_s)] + [Paragraph("", td_s) for _ in range(5)])
    a_tbl = Table(a_table_data, colWidths=[70, 95, 75, 75, 145, 76], repeatRows=1)
    a_styles = [
        ("BACKGROUND", (0, 0), (-1, 0), accent),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#e5e5e5")),
    ]
    for idx in range(1, len(a_table_data)):
        a_styles.append(("BACKGROUND", (0, idx), (-1, idx), colors.white if idx % 2 == 1 else colors.HexColor("#fafafa")))
    a_tbl.setStyle(TableStyle(a_styles))
    story.append(a_tbl)

    story.append(Spacer(1, 14))
    f_text = brand.get("footer") or BRANDING_DEFAULT["footer"]
    story.append(Paragraph(f_text, ParagraphStyle("rep_ft", parent=styles["Italic"], textColor=colors.HexColor("#737373"), fontSize=7.5, leading=9.5)))

    doc.build(story)
    buf.seek(0)
    return buf.getvalue()

def build_single_asset_csv(asset: dict, events: list, maints: list, bks: list, auds: list) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["ASSET LIFECYCLE REPORT", asset.get("name", ""), f"Tag: {asset.get('tag', '')}"])
    writer.writerow([])
    writer.writerow(["--- ASSET PROFILE ---"])
    for k in ["tag", "name", "category", "department", "location", "status", "holder", "serial", "bookable", "purchase_cost", "purchase_date", "supplier", "warranty_end"]:
        writer.writerow([k.replace("_", " ").title(), asset.get(k, "")])
    writer.writerow([])
    writer.writerow(["--- LIFECYCLE & ACTIVITY TRAIL ---"])
    writer.writerow(["Timestamp (UTC)", "Actor", "Action", "Entity Type", "Entity ID", "Notes"])
    for e in events:
        writer.writerow([e.get("timestamp", ""), e.get("actor", ""), e.get("action", ""), e.get("entity_type", ""), e.get("entity_id", ""), str(e.get("metadata", ""))])
    writer.writerow([])
    writer.writerow(["--- MAINTENANCE HISTORY ---"])
    writer.writerow(["Request ID", "Priority", "Status", "Description", "Raised By", "Created At", "Resolved At"])
    for m in maints:
        writer.writerow([m.get("request_id", ""), m.get("priority", ""), m.get("status", ""), m.get("description", ""), m.get("raised_by", ""), m.get("created_at", ""), m.get("resolved_at", "")])
    writer.writerow([])
    writer.writerow(["--- BOOKING UTILIZATION ---"])
    writer.writerow(["Booking ID", "Date", "Start Time", "End Time", "Purpose / Event", "Requested By", "Status"])
    for b in bks:
        writer.writerow([b.get("booking_id", ""), b.get("date", ""), b.get("start_time", ""), b.get("end_time", ""), b.get("event_title") or b.get("purpose", ""), b.get("requested_by", ""), b.get("status", "")])
    writer.writerow([])
    writer.writerow(["--- AUDIT VERIFICATIONS ---"])
    writer.writerow(["Audit ID", "Department", "Period", "Verification", "Note", "Closed At"])
    for a in auds:
        for it in a.get("items", []):
            if it.get("asset_id") == asset.get("asset_id") or it.get("tag") == asset.get("tag"):
                writer.writerow([a.get("audit_id", ""), a.get("department", ""), a.get("period", ""), it.get("verification", ""), it.get("note", ""), a.get("closed_at", "")])
    buf.seek(0)
    return buf.getvalue()

# --- 1. Department Asset Register ---
@api.get("/reports/department/{dept}/assets")
async def report_department_assets(dept: str, format: str = "csv", user=Depends(require_permission("reports"))):
    query = {"department": {"$regex": f"^{re.escape(dept)}$", "$options": "i"}}
    assets = [clean(x) for x in await db.assets.find(query, {"_id": 0}).sort("name", 1).to_list(1000)]
    brand = await get_active_brand()
    headers = ["Tag", "Name", "Category", "Location", "Status", "Holder", "Serial", "Purchase Date", "Cost"]
    rows = []
    for a in assets:
        cost_str = f"{a.get('purchase_cost', 0):,.2f}" if a.get("purchase_cost") else "—"
        rows.append([a.get("tag", ""), a.get("name", ""), a.get("category", ""), a.get("location", ""), a.get("status", ""), a.get("holder") or "—", a.get("serial", ""), a.get("purchase_date") or "—", cost_str])

    if format == "json":
        return {
            "title": f"{dept} Asset Register",
            "department": dept,
            "total": len(assets),
            "allocated": sum(1 for x in assets if x.get("status") == "Allocated"),
            "available": sum(1 for x in assets if x.get("status") == "Available"),
            "maintenance": sum(1 for x in assets if x.get("status") == "Under Maintenance"),
            "items": assets,
            "headers": headers,
            "rows": rows
        }
    if format == "csv":
        csv_data = build_report_csv(headers, rows)
        await log_event(user, "department asset report downloaded", "report", dept, metadata={"format": "csv"})
        filename = f"assetflow_{dept.lower().replace(' ', '_')}_assets.csv"
        return StreamingResponse(iter([csv_data]), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="{filename}"'})
    if format == "pdf":
        meta = [
            ("Department", dept),
            ("Total Assets", len(assets)),
            ("Generated (UTC)", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")),
            ("Prepared By", user.get("name", "User")),
            ("Allocated", sum(1 for x in assets if x.get("status") == "Allocated")),
            ("Available", sum(1 for x in assets if x.get("status") == "Available")),
        ]
        col_w = [65, 110, 70, 75, 55, 65, 55, 55, 45]
        pdf_bytes = build_generic_report_pdf(f"{dept} · Asset Register", "Departmental inventory breakdown and allocation status", meta, headers, rows, brand, col_widths=col_w)
        await log_event(user, "department asset report downloaded", "report", dept, metadata={"format": "pdf"})
        filename = f"assetflow_{dept.lower().replace(' ', '_')}_assets.pdf"
        return StreamingResponse(iter([pdf_bytes]), media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{filename}"'})
    raise HTTPException(400, "Unsupported format. Use csv, pdf or json.")

# --- 2. Department Maintenance Log ---
@api.get("/reports/department/{dept}/maintenance")
async def report_department_maintenance(dept: str, format: str = "csv", user=Depends(require_permission("reports"))):
    dept_assets = [clean(x) for x in await db.assets.find({"department": {"$regex": f"^{re.escape(dept)}$", "$options": "i"}}, {"_id": 0, "asset_id": 1, "name": 1, "tag": 1}).to_list(1000)]
    asset_map = {a["asset_id"]: a for a in dept_assets}
    query = {"$or": [{"asset_id": {"$in": list(asset_map.keys())}}, {"department": {"$regex": f"^{re.escape(dept)}$", "$options": "i"}}]}
    maints = [clean(x) for x in await db.maintenance.find(query, {"_id": 0}).sort("created_at", -1).to_list(1000)]
    brand = await get_active_brand()
    headers = ["Request ID", "Tag", "Asset Name", "Description", "Priority", "Status", "Raised By", "Created", "Resolved"]
    rows = []
    for m in maints:
        ast = asset_map.get(m.get("asset_id")) or {}
        rows.append([
            m.get("request_id", ""),
            ast.get("tag", m.get("asset_id", "")),
            ast.get("name", "—"),
            m.get("description", ""),
            m.get("priority", "Medium"),
            m.get("status", "Open"),
            m.get("raised_by", ""),
            (m.get("created_at") or "")[:10],
            (m.get("resolved_at") or "—")[:10]
        ])

    if format == "json":
        return {
            "title": f"{dept} Maintenance Work Orders",
            "department": dept,
            "total": len(maints),
            "open": sum(1 for m in maints if m.get("status") not in ["Resolved", "Rejected"]),
            "resolved": sum(1 for m in maints if m.get("status") == "Resolved"),
            "items": maints,
            "headers": headers,
            "rows": rows
        }
    if format == "csv":
        csv_data = build_report_csv(headers, rows)
        await log_event(user, "department maintenance report downloaded", "report", dept, metadata={"format": "csv"})
        filename = f"assetflow_{dept.lower().replace(' ', '_')}_maintenance.csv"
        return StreamingResponse(iter([csv_data]), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="{filename}"'})
    if format == "pdf":
        meta = [
            ("Department", dept),
            ("Total Requests", len(maints)),
            ("Generated (UTC)", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")),
            ("Prepared By", user.get("name", "User")),
            ("Open / In Progress", sum(1 for m in maints if m.get("status") not in ["Resolved", "Rejected"])),
            ("Resolved", sum(1 for m in maints if m.get("status") == "Resolved")),
        ]
        col_w = [60, 55, 85, 120, 45, 50, 65, 50, 50]
        pdf_bytes = build_generic_report_pdf(f"{dept} · Maintenance Log", "Work orders, repair history, and resolution tracking", meta, headers, rows, brand, col_widths=col_w)
        await log_event(user, "department maintenance report downloaded", "report", dept, metadata={"format": "pdf"})
        filename = f"assetflow_{dept.lower().replace(' ', '_')}_maintenance.pdf"
        return StreamingResponse(iter([pdf_bytes]), media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{filename}"'})
    raise HTTPException(400, "Unsupported format. Use csv, pdf or json.")

# --- 3. Department Booking Log ---
@api.get("/reports/department/{dept}/bookings")
async def report_department_bookings(dept: str, format: str = "csv", user=Depends(require_permission("reports"))):
    dept_assets = [clean(x) for x in await db.assets.find({"department": {"$regex": f"^{re.escape(dept)}$", "$options": "i"}}, {"_id": 0, "asset_id": 1}).to_list(1000)]
    asset_ids = [a["asset_id"] for a in dept_assets]
    query = {"$or": [{"department": {"$regex": f"^{re.escape(dept)}$", "$options": "i"}}, {"resource_id": {"$in": asset_ids}}]}
    bks = [clean(x) for x in await db.bookings.find(query, {"_id": 0}).sort([("date", -1), ("start_time", 1)]).to_list(1000)]
    brand = await get_active_brand()
    headers = ["Booking ID", "Resource / Room", "Date", "Time Slot", "Event / Purpose", "Department", "Requested By", "Attendees", "Status"]
    rows = []
    for b in bks:
        rows.append([
            b.get("booking_id", ""),
            b.get("resource_name") or b.get("resource_id", ""),
            b.get("date", ""),
            f"{b.get('start_time','')} - {b.get('end_time','')}",
            b.get("event_title") or b.get("purpose", ""),
            b.get("department", ""),
            b.get("requested_by", ""),
            str(b.get("attendees", 0)),
            b.get("status", "Confirmed")
        ])

    if format == "json":
        return {
            "title": f"{dept} Resource Booking Report",
            "department": dept,
            "total": len(bks),
            "confirmed": sum(1 for b in bks if b.get("status") == "Confirmed"),
            "items": bks,
            "headers": headers,
            "rows": rows
        }
    if format == "csv":
        csv_data = build_report_csv(headers, rows)
        await log_event(user, "department booking report downloaded", "report", dept, metadata={"format": "csv"})
        filename = f"assetflow_{dept.lower().replace(' ', '_')}_bookings.csv"
        return StreamingResponse(iter([csv_data]), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="{filename}"'})
    if format == "pdf":
        meta = [
            ("Department", dept),
            ("Total Bookings", len(bks)),
            ("Generated (UTC)", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")),
            ("Prepared By", user.get("name", "User")),
            ("Confirmed", sum(1 for b in bks if b.get("status") == "Confirmed")),
            ("Cancelled", sum(1 for b in bks if b.get("status") == "Cancelled")),
        ]
        col_w = [60, 95, 55, 65, 110, 60, 65, 40, 50]
        pdf_bytes = build_generic_report_pdf(f"{dept} · Booking Report", "Space & equipment reservation logs and attendee density", meta, headers, rows, brand, col_widths=col_w)
        await log_event(user, "department booking report downloaded", "report", dept, metadata={"format": "pdf"})
        filename = f"assetflow_{dept.lower().replace(' ', '_')}_bookings.pdf"
        return StreamingResponse(iter([pdf_bytes]), media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{filename}"'})
    raise HTTPException(400, "Unsupported format. Use csv, pdf or json.")

# --- 4. Assets Filtered by Status ---
@api.get("/reports/assets-by-status")
async def report_assets_by_status(status: str = "All", department: str = "All", format: str = "csv", user=Depends(require_permission("reports"))):
    query = {}
    if status != "All": query["status"] = status
    if department != "All": query["department"] = department
    assets = [clean(x) for x in await db.assets.find(query, {"_id": 0}).sort("name", 1).to_list(1000)]
    brand = await get_active_brand()
    headers = ["Tag", "Name", "Department", "Location", "Category", "Status", "Holder", "Serial"]
    rows = []
    for a in assets:
        rows.append([a.get("tag", ""), a.get("name", ""), a.get("department", ""), a.get("location", ""), a.get("category", ""), a.get("status", ""), a.get("holder") or "—", a.get("serial", "")])

    title = f"Assets Report · Status: {status}" if status != "All" else "Campus Assets by Status"
    if format == "json":
        return {"title": title, "status": status, "department": department, "total": len(assets), "items": assets, "headers": headers, "rows": rows}
    if format == "csv":
        csv_data = build_report_csv(headers, rows)
        await log_event(user, "status asset report downloaded", "report", status, metadata={"format": "csv"})
        filename = f"assetflow_assets_status_{status.lower().replace(' ', '_')}.csv"
        return StreamingResponse(iter([csv_data]), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="{filename}"'})
    if format == "pdf":
        meta = [
            ("Filter Status", status),
            ("Department Filter", department),
            ("Total Records", len(assets)),
            ("Prepared By", user.get("name", "User")),
            ("Generated (UTC)", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")),
            ("Format Target", "Campus Audit"),
        ]
        col_w = [65, 110, 75, 75, 70, 55, 70, 60]
        pdf_bytes = build_generic_report_pdf(title, f"Inventory filtered by operational status '{status}' across departments", meta, headers, rows, brand, col_widths=col_w)
        await log_event(user, "status asset report downloaded", "report", status, metadata={"format": "pdf"})
        filename = f"assetflow_assets_status_{status.lower().replace(' ', '_')}.pdf"
        return StreamingResponse(iter([pdf_bytes]), media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{filename}"'})
    raise HTTPException(400, "Unsupported format. Use csv, pdf or json.")

# --- 5. Assets Filtered by Category ---
@api.get("/reports/assets-by-category")
async def report_assets_by_category(category: str = "All", department: str = "All", format: str = "csv", user=Depends(require_permission("reports"))):
    query = {}
    if category != "All": query["category"] = category
    if department != "All": query["department"] = department
    assets = [clean(x) for x in await db.assets.find(query, {"_id": 0}).sort("name", 1).to_list(1000)]
    brand = await get_active_brand()
    headers = ["Tag", "Name", "Category", "Department", "Location", "Status", "Holder", "Serial"]
    rows = []
    for a in assets:
        rows.append([a.get("tag", ""), a.get("name", ""), a.get("category", ""), a.get("department", ""), a.get("location", ""), a.get("status", ""), a.get("holder") or "—", a.get("serial", "")])

    title = f"Assets Report · Category: {category}" if category != "All" else "Campus Assets by Category"
    if format == "json":
        return {"title": title, "category": category, "department": department, "total": len(assets), "items": assets, "headers": headers, "rows": rows}
    if format == "csv":
        csv_data = build_report_csv(headers, rows)
        await log_event(user, "category asset report downloaded", "report", category, metadata={"format": "csv"})
        filename = f"assetflow_assets_cat_{category.lower().replace(' ', '_')}.csv"
        return StreamingResponse(iter([csv_data]), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="{filename}"'})
    if format == "pdf":
        meta = [
            ("Category", category),
            ("Department Filter", department),
            ("Total Records", len(assets)),
            ("Prepared By", user.get("name", "User")),
            ("Generated (UTC)", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")),
            ("Format Target", "Campus Inventory"),
        ]
        col_w = [65, 110, 70, 75, 75, 55, 70, 60]
        pdf_bytes = build_generic_report_pdf(title, f"Inventory filtered by category '{category}' across departments", meta, headers, rows, brand, col_widths=col_w)
        await log_event(user, "category asset report downloaded", "report", category, metadata={"format": "pdf"})
        filename = f"assetflow_assets_cat_{category.lower().replace(' ', '_')}.pdf"
        return StreamingResponse(iter([pdf_bytes]), media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{filename}"'})
    raise HTTPException(400, "Unsupported format. Use csv, pdf or json.")

# --- 6. User Asset Holding Report (No-Dues / Clearance) ---
@api.get("/reports/user-assets/{user_id}")
async def report_user_assets(user_id: str, format: str = "csv", user=Depends(require_permission("reports"))):
    target_user = await db.users.find_one({"$or": [{"user_id": user_id}, {"email": user_id}]}, {"_id": 0})
    target_name = target_user.get("name") if target_user else user_id
    query = {"$or": [{"holder": target_name}, {"holder": {"$regex": f"^{re.escape(target_name)}$", "$options": "i"}}, {"holder_id": user_id}]}
    assets = [clean(x) for x in await db.assets.find(query, {"_id": 0}).sort("name", 1).to_list(200)]
    brand = await get_active_brand()
    headers = ["Tag", "Name", "Category", "Department", "Location", "Status", "Serial", "Expected Return"]
    rows = []
    for a in assets:
        rows.append([a.get("tag", ""), a.get("name", ""), a.get("category", ""), a.get("department", ""), a.get("location", ""), a.get("status", ""), a.get("serial", ""), a.get("expected_return_at") or "—"])

    title = f"Asset Holding Roster · {target_name}"
    if format == "json":
        return {"title": title, "user": target_user or {"name": target_name, "user_id": user_id}, "total": len(assets), "items": assets, "headers": headers, "rows": rows}
    if format == "csv":
        csv_data = build_report_csv(headers, rows)
        await log_event(user, "user asset report downloaded", "report", user_id, metadata={"format": "csv"})
        filename = f"assetflow_user_{user_id}_assets.csv"
        return StreamingResponse(iter([csv_data]), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="{filename}"'})
    if format == "pdf":
        meta = [
            ("Employee / Student", target_name),
            ("Department", (target_user or {}).get("department", "—")),
            ("Role", (target_user or {}).get("role", "—")),
            ("Total Held Assets", len(assets)),
            ("Generated (UTC)", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")),
            ("Clearance Status", "PENDING RETURN" if len(assets) > 0 else "CLEARED (0 ASSETS)"),
        ]
        col_w = [65, 115, 75, 70, 75, 55, 60, 65]
        pdf_bytes = build_generic_report_pdf(title, "Personal asset allocation certificate & no-dues verification extract", meta, headers, rows, brand, col_widths=col_w)
        await log_event(user, "user asset report downloaded", "report", user_id, metadata={"format": "pdf"})
        filename = f"assetflow_user_{user_id}_assets.pdf"
        return StreamingResponse(iter([pdf_bytes]), media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{filename}"'})
    raise HTTPException(400, "Unsupported format. Use csv, pdf or json.")

# --- 7. Single Asset Lifecycle Report (Full Lifecycle Trace) ---
@api.get("/reports/asset/{asset_id}")
async def report_single_asset(asset_id: str, format: str = "csv", user=Depends(require_permission("reports"))):
    asset = clean(await db.assets.find_one({"$or": [{"asset_id": asset_id}, {"tag": asset_id}]}, {"_id": 0}))
    if not asset:
        raise HTTPException(404, "Asset not found")

    aid = asset["asset_id"]
    events = [clean(x) for x in await db.activity.find({"entity_id": aid}, {"_id": 0}).sort("timestamp", 1).to_list(200)]
    maints = [clean(x) for x in await db.maintenance.find({"asset_id": aid}, {"_id": 0}).sort("created_at", -1).to_list(100)]
    bks = [clean(x) for x in await db.bookings.find({"resource_id": aid}, {"_id": 0}).sort("date", -1).to_list(100)]
    auds = [clean(x) for x in await db.audits.find({"items.asset_id": aid}, {"_id": 0}).sort("created_at", -1).to_list(50)]
    brand = await get_active_brand()

    if format == "json":
        return {
            "asset": asset,
            "activity": events,
            "maintenance": maints,
            "bookings": bks,
            "audits": auds,
            "metrics": {
                "total_events": len(events),
                "total_maintenance": len(maints),
                "open_maintenance": sum(1 for m in maints if m.get("status") not in ["Resolved", "Rejected"]),
                "total_bookings": len(bks),
                "audit_verifications": sum(1 for a in auds for it in a.get("items", []) if it.get("asset_id") == aid)
            }
        }
    if format == "csv":
        csv_data = build_single_asset_csv(asset, events, maints, bks, auds)
        await log_event(user, "single asset report downloaded", "report", aid, metadata={"format": "csv"})
        filename = f"assetflow_asset_{asset.get('tag', aid)}_lifecycle.csv"
        return StreamingResponse(iter([csv_data]), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="{filename}"'})
    if format == "pdf":
        pdf_bytes = build_single_asset_pdf(asset, events, maints, bks, auds, brand, user.get("name", "User"))
        await log_event(user, "single asset report downloaded", "report", aid, metadata={"format": "pdf"})
        filename = f"assetflow_asset_{asset.get('tag', aid)}_lifecycle.pdf"
        return StreamingResponse(iter([pdf_bytes]), media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{filename}"'})
    raise HTTPException(400, "Unsupported format. Use csv, pdf or json.")

# --- 8. Admin Report Templates System ---
@api.get("/reports/templates/schema/{source}")
async def report_template_schema(source: str, user=Depends(require_permission("reports"))):
    if source not in DATA_SOURCES_SCHEMA:
        raise HTTPException(400, f"Unknown data source '{source}'. Available: {list(DATA_SOURCES_SCHEMA.keys())}")
    return DATA_SOURCES_SCHEMA[source]

@api.get("/reports/templates")
async def list_report_templates(user=Depends(require_permission("reports"))):
    query = {"is_active": {"$ne": False}}
    # Non-admins only see templates that include their role or "All roles"
    if user.get("role") != "Admin":
        query["$or"] = [
            {"access_roles": user.get("role")},
            {"access_roles": "All roles"},
            {"access_roles": "All"}
        ]
    templates = [clean(x) for x in await db.report_templates.find(query, {"_id": 0}).sort("name", 1).to_list(100)]
    return templates

@api.post("/reports/templates")
async def create_report_template(payload: TemplateCreate, user=Depends(require_permission("admin"))):
    if payload.data_source not in DATA_SOURCES_SCHEMA:
        raise HTTPException(400, f"Invalid data source '{payload.data_source}'")
    tmpl_id = f"tmpl_{uuid.uuid4().hex[:10]}"
    now = now_iso()
    doc = {
        "template_id": tmpl_id,
        "name": payload.name.strip(),
        "description": payload.description.strip(),
        "data_source": payload.data_source,
        "columns": payload.columns,
        "filters": payload.filters,
        "sort_by": payload.sort_by,
        "sort_order": payload.sort_order,
        "access_roles": payload.access_roles or ["Admin"],
        "created_by": user["user_id"],
        "created_by_name": user.get("name", "Admin"),
        "created_at": now,
        "updated_at": now,
        "is_active": True
    }
    await db.report_templates.insert_one(doc)
    await log_event(user, "report template created", "template", tmpl_id, after={"name": doc["name"], "source": doc["data_source"]})
    return clean(doc)

@api.get("/reports/templates/{template_id}")
async def get_report_template(template_id: str, user=Depends(require_permission("reports"))):
    doc = await db.report_templates.find_one({"template_id": template_id, "is_active": {"$ne": False}}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Template not found")
    if user.get("role") != "Admin" and user.get("role") not in doc.get("access_roles", []) and "All roles" not in doc.get("access_roles", []):
        raise HTTPException(403, "You do not have access to this report template")
    return clean(doc)

@api.put("/reports/templates/{template_id}")
async def update_report_template(template_id: str, payload: TemplateUpdate, user=Depends(require_permission("admin"))):
    before = await db.report_templates.find_one({"template_id": template_id}, {"_id": 0})
    if not before:
        raise HTTPException(404, "Template not found")
    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    updates["updated_at"] = now_iso()
    await db.report_templates.update_one({"template_id": template_id}, {"$set": updates})
    after = {**before, **updates}
    await log_event(user, "report template updated", "template", template_id, before=before, after=after)
    return clean(after)

@api.delete("/reports/templates/{template_id}")
async def delete_report_template(template_id: str, user=Depends(require_permission("admin"))):
    doc = await db.report_templates.find_one({"template_id": template_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Template not found")
    await db.report_templates.update_one({"template_id": template_id}, {"$set": {"is_active": False, "updated_at": now_iso()}})
    await log_event(user, "report template deleted", "template", template_id, before={"name": doc.get("name")})
    return {"ok": True, "message": "Template removed"}

async def execute_template_query(template: dict):
    source = template.get("data_source", "assets")
    coll = getattr(db, source, db.assets)
    query = {}
    for k, v in (template.get("filters") or {}).items():
        if v and v != "All":
            if isinstance(v, str):
                query[k] = {"$regex": f"^{re.escape(v)}$", "$options": "i"}
            else:
                query[k] = v

    sort_field = template.get("sort_by") or "created_at"
    sort_dir = 1 if template.get("sort_order") == "asc" else -1

    schema = DATA_SOURCES_SCHEMA.get(source, {})
    col_labels = {c["key"]: c["label"] for c in schema.get("columns", [])}
    active_cols = template.get("columns") or [c["key"] for c in schema.get("columns", [])[:6]]

    raw_items = [clean(x) for x in await coll.find(query, {"_id": 0}).sort(sort_field, sort_dir).to_list(1500)]
    headers = [col_labels.get(k, k.replace("_", " ").title()) for k in active_cols]

    rows = []
    for item in raw_items:
        row = []
        for k in active_cols:
            val = item.get(k)
            if isinstance(val, bool): val = "Yes" if val else "No"
            elif isinstance(val, (int, float)) and "cost" in k.lower(): val = f"{val:,.2f}"
            row.append(val if val is not None else "—")
        rows.append(row)

    return {
        "source": source,
        "headers": headers,
        "active_cols": active_cols,
        "rows": rows,
        "items": raw_items,
        "total": len(raw_items)
    }

@api.get("/reports/templates/{template_id}/preview")
async def preview_report_template(template_id: str, user=Depends(require_permission("reports"))):
    doc = await db.report_templates.find_one({"template_id": template_id, "is_active": {"$ne": False}}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Template not found")
    if user.get("role") != "Admin" and user.get("role") not in doc.get("access_roles", []) and "All roles" not in doc.get("access_roles", []):
        raise HTTPException(403, "You do not have access to this report template")

    data = await execute_template_query(doc)
    return {
        "template": clean(doc),
        "total": data["total"],
        "headers": data["headers"],
        "active_cols": data["active_cols"],
        "preview_rows": data["rows"][:20],
        "preview_items": data["items"][:20]
    }

@api.get("/reports/templates/{template_id}/download")
async def download_report_template(template_id: str, format: str = "csv", user=Depends(require_permission("reports"))):
    doc = await db.report_templates.find_one({"template_id": template_id, "is_active": {"$ne": False}}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Template not found")
    if user.get("role") != "Admin" and user.get("role") not in doc.get("access_roles", []) and "All roles" not in doc.get("access_roles", []):
        raise HTTPException(403, "You do not have access to this report template")

    data = await execute_template_query(doc)
    brand = await get_active_brand()
    title = doc.get("name", "Custom Report")
    subtitle = doc.get("description") or f"Machine-generated from custom template {template_id}"
    safe_name = re.sub(r'[^a-zA-Z0-9_-]', '_', title.lower())

    if format == "csv":
        csv_data = build_report_csv(data["headers"], data["rows"])
        await log_event(user, "custom report downloaded", "template", template_id, metadata={"format": "csv", "name": title})
        return StreamingResponse(iter([csv_data]), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="assetflow_{safe_name}.csv"'})

    if format == "pdf":
        meta = [
            ("Template", title),
            ("Data Source", DATA_SOURCES_SCHEMA.get(doc.get("data_source"), {}).get("label", doc.get("data_source", ""))),
            ("Total Records", data["total"]),
            ("Prepared By", user.get("name", "User")),
            ("Generated (UTC)", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")),
            ("Filters", ", ".join(f"{k}={v}" for k, v in (doc.get("filters") or {}).items()) or "None"),
        ]
        pdf_bytes = build_generic_report_pdf(title, subtitle, meta, data["headers"], data["rows"], brand)
        await log_event(user, "custom report downloaded", "template", template_id, metadata={"format": "pdf", "name": title})
        return StreamingResponse(iter([pdf_bytes]), media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="assetflow_{safe_name}.pdf"'})

    raise HTTPException(400, "Unsupported format. Use csv or pdf.")


@api.get("/notifications")
async def notifications(user=Depends(current_user)):
    items = []
    high_maint = await db.maintenance.find({"priority": "High", "status": {"$ne": "Resolved"}}, {"_id": 0}).sort("created_at", -1).to_list(20)
    for m in high_maint:
        items.append({"id": f"maint_{m['request_id']}", "kind": "maintenance", "title": f"High-priority repair · {m['asset_id']}", "detail": m["description"], "when": m["created_at"], "link": "/maintenance"})
    from datetime import date as _date
    today = datetime.now(timezone.utc).date()
    upcoming_cutoff = (today + timedelta(days=3)).isoformat()
    today_iso = today.isoformat()
    bookings = await db.bookings.find({"date": {"$gte": today_iso, "$lte": upcoming_cutoff}, "status": "Confirmed"}, {"_id": 0}).sort([("date", 1), ("start_time", 1)]).to_list(20)
    for b in bookings:
        items.append({"id": f"book_{b['booking_id']}", "kind": "booking", "title": f"Upcoming booking · {b['resource_id']}", "detail": f"{b['date']} {b['start_time']}–{b['end_time']} · {b.get('purpose','')}", "when": b["created_at"], "link": "/bookings"})
    if user.get("role") == "Admin":
        pending = await db.users.find({"status": "Pending"}, {"_id": 0}).sort("created_at", -1).to_list(20)
        for p in pending:
            items.append({"id": f"role_{p['user_id']}", "kind": "approval", "title": f"Role approval pending · {p.get('name','New user')}", "detail": f"{p.get('email','')} · currently {p.get('role','Student')}", "when": p.get("created_at", now_iso()), "link": "/admin"})
    open_audits = await db.audits.find({"status": "Open"}, {"_id": 0}).sort("created_at", -1).to_list(10)
    for a in open_audits:
        pending_items = sum(1 for i in a.get("items", []) if i.get("verification") == "Pending")
        if pending_items:
            items.append({"id": f"audit_{a['audit_id']}", "kind": "audit", "title": f"Audit cycle open · {a['department']}", "detail": f"{pending_items} items pending verification", "when": a["created_at"], "link": "/audits"})
    items.sort(key=lambda x: x["when"], reverse=True)
    state = await db.notification_state.find_one({"user_id": user["user_id"]}, {"_id": 0}) or {}
    last_seen = state.get("last_seen", "1970-01-01T00:00:00+00:00")
    unread = sum(1 for x in items if x["when"] > last_seen)
    return {"items": items[:30], "unread": unread, "last_seen": last_seen}

@api.post("/notifications/mark-all-read")
async def mark_notifications_read(user=Depends(current_user)):
    await db.notification_state.update_one({"user_id": user["user_id"]}, {"$set": {"last_seen": now_iso()}}, upsert=True)
    return {"ok": True}

@api.get("/admin/role-preview/{role}")
async def role_preview(role: str, user=Depends(require_permission("admin"))):
    if role not in ROLES: raise HTTPException(400, "Unknown role")
    perms = sorted(ROLE_PERMISSIONS.get(role, set()))
    labels = {"admin": "Admin console · organization setup · role approvals", "asset_write": "Register, update, check in/out assets", "maintenance_write": "Raise & advance maintenance work orders", "booking": "Reserve rooms and equipment", "audit": "Run and close audit cycles", "nodues": "Manage student no-dues clearance", "reports": "Reports, analytics & accreditation exports"}
    nav_paths = {"Admin": ["/dashboard","/inventory","/bookings","/maintenance","/audits","/nodues","/reports","/activity","/admin"], "Asset Manager": ["/dashboard","/inventory","/bookings","/maintenance","/audits","/reports","/activity"], "HOD": ["/dashboard","/inventory","/bookings","/maintenance","/reports","/activity"], "Employee": ["/dashboard","/inventory","/bookings","/maintenance","/reports"], "Student": ["/dashboard","/inventory","/bookings","/maintenance"]}
    return {"role": role, "permissions": perms, "capabilities": [labels[p] for p in perms if p in labels], "visible_pages": nav_paths.get(role, [])}

@api.get("/assets/by-tag/{tag}")
async def asset_by_tag(tag: str, user=Depends(current_user)):
    asset = await db.assets.find_one({"tag": tag}, {"_id": 0})
    if not asset: raise HTTPException(404, "No asset with this tag")
    return clean(asset)

# --- Cloudinary photo attachments ---
ALLOWED_UPLOAD_FOLDERS = ("assetflow/maintenance/", "assetflow/audits/", "assetflow/branding/")

@api.get("/uploads/signature")
async def cloudinary_signature(folder: str, user=Depends(current_user)):
    if not folder.startswith(ALLOWED_UPLOAD_FOLDERS):
        raise HTTPException(400, "Invalid folder path")
    if folder.startswith("assetflow/branding/") and user.get("role") != "Admin":
        raise HTTPException(403, "Only admins can upload branding assets")
    ts = int(time.time())
    params = {"timestamp": ts, "folder": folder}
    signature = cloudinary.utils.api_sign_request(params, os.environ.get("CLOUDINARY_API_SECRET"))
    return {"signature": signature, "timestamp": ts, "cloud_name": os.environ.get("CLOUDINARY_CLOUD_NAME"), "api_key": os.environ.get("CLOUDINARY_API_KEY"), "folder": folder}

class PhotoAttach(BaseModel):
    public_id: str = Field(min_length=3, max_length=200)
    secure_url: str = Field(min_length=10, max_length=500)
    width: Optional[int] = None
    height: Optional[int] = None

@api.post("/maintenance/{request_id}/photos")
async def add_maintenance_photo(request_id: str, payload: PhotoAttach, user=Depends(require_permission("maintenance_write"))):
    doc = await db.maintenance.find_one({"request_id": request_id}, {"_id": 0})
    if not doc: raise HTTPException(404, "Request not found")
    if not payload.secure_url.startswith("https://res.cloudinary.com/"): raise HTTPException(400, "Only Cloudinary URLs allowed")
    photo = {"public_id": payload.public_id, "url": payload.secure_url, "width": payload.width, "height": payload.height, "uploaded_by": user.get("name"), "uploaded_at": now_iso()}
    await db.maintenance.update_one({"request_id": request_id}, {"$push": {"photos": photo}})
    await log_event(user, "maintenance photo attached", "maintenance", request_id, metadata={"public_id": payload.public_id})
    return {"ok": True, "photo": photo}

@api.delete("/maintenance/{request_id}/photos/{public_id:path}")
async def remove_maintenance_photo(request_id: str, public_id: str, user=Depends(require_permission("maintenance_write"))):
    doc = await db.maintenance.find_one({"request_id": request_id}, {"_id": 0})
    if not doc: raise HTTPException(404, "Request not found")
    if user.get("role") not in {"Admin", "Asset Manager", "HOD"} and doc.get("raised_by_id") != user.get("user_id"):
        raise HTTPException(403, "Cannot delete another user's photo")
    try: cloudinary.uploader.destroy(public_id, invalidate=True)
    except Exception as e: logger.warning(f"Cloudinary destroy failed for {public_id}: {e}")
    await db.maintenance.update_one({"request_id": request_id}, {"$pull": {"photos": {"public_id": public_id}}})
    await log_event(user, "maintenance photo removed", "maintenance", request_id, metadata={"public_id": public_id})
    return {"ok": True}

@api.post("/audits/{audit_id}/items/{asset_id}/photos")
async def add_audit_photo(audit_id: str, asset_id: str, payload: PhotoAttach, user=Depends(require_permission("audit"))):
    doc = await db.audits.find_one({"audit_id": audit_id, "items.asset_id": asset_id}, {"_id": 0})
    if not doc: raise HTTPException(404, "Audit item not found")
    if not payload.secure_url.startswith("https://res.cloudinary.com/"): raise HTTPException(400, "Only Cloudinary URLs allowed")
    photo = {"public_id": payload.public_id, "url": payload.secure_url, "uploaded_by": user.get("name"), "uploaded_at": now_iso()}
    await db.audits.update_one({"audit_id": audit_id, "items.asset_id": asset_id}, {"$push": {"items.$.photos": photo}})
    await log_event(user, "audit photo attached", "audit", audit_id, metadata={"asset_id": asset_id, "public_id": payload.public_id})
    return {"ok": True, "photo": photo}

# --- Weekly digest ---
@api.get("/digest/weekly")
async def weekly_digest(user=Depends(require_permission("admin"))):
    now = datetime.now(timezone.utc)
    week_ago = (now - timedelta(days=7)).isoformat()
    upcoming_end = (now.date() + timedelta(days=7)).isoformat()
    today_iso = now.date().isoformat()
    open_maintenance = await db.maintenance.find({"status": {"$nin": ["Resolved", "Rejected"]}}, {"_id": 0}).sort("priority", -1).to_list(50)
    resolved_this_week = await db.maintenance.count_documents({"status": "Resolved", "resolved_at": {"$gte": week_ago}})
    pending_users = await db.users.find({"status": "Pending"}, {"_id": 0, "password_hash": 0}).to_list(50)
    upcoming_bookings = await db.bookings.find({"date": {"$gte": today_iso, "$lte": upcoming_end}, "status": "Confirmed"}, {"_id": 0}).sort([("date", 1), ("start_time", 1)]).to_list(50)
    open_audits = await db.audits.find({"status": "Open"}, {"_id": 0}).to_list(50)
    assets_total = await db.assets.count_documents({})
    allocated = await db.assets.count_documents({"status": "Allocated"})
    utilization = round((allocated / assets_total) * 100) if assets_total else 0
    events_this_week = await db.activity.count_documents({"timestamp": {"$gte": week_ago}})
    return {
        "generated_at": now.isoformat(),
        "week_of": (now.date() - timedelta(days=now.weekday())).isoformat(),
        "kpis": {"open_maintenance": len(open_maintenance), "resolved_this_week": resolved_this_week, "pending_approvals": len(pending_users), "upcoming_bookings": len(upcoming_bookings), "open_audits": len(open_audits), "utilization": utilization, "activity_events": events_this_week},
        "open_maintenance": [clean(m) for m in open_maintenance[:10]],
        "pending_users": [clean(u) for u in pending_users[:10]],
        "upcoming_bookings": [clean(b) for b in upcoming_bookings[:10]],
        "open_audits": [{"audit_id": a["audit_id"], "department": a["department"], "period": a["period"], "pending_items": sum(1 for i in a.get("items", []) if i.get("verification") == "Pending")} for a in open_audits[:10]],
    }

# --- NAAC branding / cover sheet ---
class BrandingUpdate(BaseModel):
    institution_name: str = Field(min_length=2, max_length=140)
    tagline: str = Field(default="", max_length=180)
    accreditation_body: str = Field(default="NAAC / NBA", max_length=80)
    footer: str = Field(default="", max_length=240)
    accent_color: str = Field(default="#171717", pattern=r"^#[0-9a-fA-F]{6}$")
    logo_url: str = Field(default="", max_length=500)

    @field_validator("institution_name", "tagline", "accreditation_body", "footer", "logo_url")
    @classmethod
    def _strip(cls, v: str) -> str: return (v or "").strip()

BRANDING_DEFAULT = {"institution_name": "AssetFlow Campus", "tagline": "Every asset. Accountable.", "accreditation_body": "NAAC / NBA", "footer": "This report is a machine-generated snapshot for accreditation review. Figures are drawn from AssetFlow Campus activity logs and can be re-verified from the workspace.", "accent_color": "#171717", "logo_url": ""}

@api.get("/admin/branding")
async def get_branding(user=Depends(current_user)):
    doc = await db.branding.find_one({"_id": "singleton"}) or {}
    return {**BRANDING_DEFAULT, **{k: v for k, v in doc.items() if k != "_id"}}

@api.put("/admin/branding")
async def update_branding(payload: BrandingUpdate, user=Depends(require_permission("admin"))):
    data = payload.model_dump()
    await db.branding.update_one({"_id": "singleton"}, {"$set": {**data, "updated_at": now_iso(), "updated_by": user["name"]}}, upsert=True)
    await log_event(user, "branding updated", "branding", "singleton", after=data)
    return {**BRANDING_DEFAULT, **data}

# --- Web push notifications ---
class PushSub(BaseModel):
    endpoint: str = Field(min_length=10, max_length=800)
    keys: dict

@api.get("/push/public-key")
async def push_public_key():
    return {"key": os.environ.get("VAPID_PUBLIC_KEY", "")}

@api.post("/push/subscribe")
async def push_subscribe(payload: PushSub, user=Depends(current_user)):
    await db.push_subs.update_one(
        {"endpoint": payload.endpoint},
        {"$set": {"endpoint": payload.endpoint, "keys": payload.keys, "user_id": user["user_id"], "user_name": user.get("name"), "role": user.get("role"), "created_at": now_iso()}},
        upsert=True,
    )
    return {"ok": True}

@api.post("/push/unsubscribe")
async def push_unsubscribe(payload: PushSub, user=Depends(current_user)):
    await db.push_subs.delete_one({"endpoint": payload.endpoint, "user_id": user["user_id"]})
    return {"ok": True}

async def send_push_to_role(roles: List[str], title: str, body: str, url: str = "/dashboard"):
    priv = os.environ.get("VAPID_PRIVATE_KEY"); pub = os.environ.get("VAPID_PUBLIC_KEY"); subj = os.environ.get("VAPID_SUBJECT")
    if not priv or not pub: return 0
    import json as _json
    try: from pywebpush import webpush, WebPushException
    except Exception: return 0
    sent = 0
    async for sub in db.push_subs.find({"role": {"$in": roles}}, {"_id": 0}):
        try:
            webpush(subscription_info={"endpoint": sub["endpoint"], "keys": sub["keys"]}, data=_json.dumps({"title": title, "body": body, "url": url}), vapid_private_key=priv, vapid_claims={"sub": subj or "mailto:admin@example.com"})
            sent += 1
        except WebPushException as e:
            if getattr(e, "response", None) is not None and e.response.status_code in (404, 410):
                await db.push_subs.delete_one({"endpoint": sub["endpoint"]})
        except Exception: pass
    return sent

# --- Delegation slots ---
class DelegationCreate(BaseModel):
    deputy_id: str = Field(min_length=3, max_length=80)
    start_at: str = Field(min_length=10, max_length=40)
    end_at: str = Field(min_length=10, max_length=40)
    note: str = Field(default="", max_length=200)

    @field_validator("deputy_id", "start_at", "end_at", "note")
    @classmethod
    def _strip(cls, v: str) -> str: return (v or "").strip()

@api.get("/admin/delegations")
async def list_delegations(user=Depends(require_permission("admin"))):
    return [clean(x) for x in await db.delegations.find({}, {"_id": 0}).sort("start_at", -1).to_list(200)]

@api.post("/admin/delegations")
async def create_delegation(payload: DelegationCreate, user=Depends(require_permission("admin"))):
    try: sa = datetime.fromisoformat(payload.start_at); ea = datetime.fromisoformat(payload.end_at)
    except Exception: raise HTTPException(400, "start_at and end_at must be ISO datetimes")
    if ea <= sa: raise HTTPException(400, "end_at must be after start_at")
    deputy = await db.users.find_one({"user_id": payload.deputy_id}, {"_id": 0, "password_hash": 0})
    if not deputy: raise HTTPException(404, "Deputy user not found")
    if deputy["user_id"] == user["user_id"]: raise HTTPException(400, "Cannot delegate to yourself")
    item = {"delegation_id": f"deleg_{uuid.uuid4().hex[:10]}", "admin_id": user["user_id"], "admin_name": user.get("name"), "deputy_id": deputy["user_id"], "deputy_name": deputy.get("name"), "deputy_original_role": deputy.get("role"), "start_at": payload.start_at, "end_at": payload.end_at, "note": payload.note, "status": "Scheduled", "created_at": now_iso()}
    await db.delegations.insert_one(item)
    await log_event(user, "delegation scheduled", "delegation", item["delegation_id"], after=item)
    return clean(item)

@api.delete("/admin/delegations/{delegation_id}")
async def revoke_delegation(delegation_id: str, user=Depends(require_permission("admin"))):
    before = clean(await db.delegations.find_one({"delegation_id": delegation_id}, {"_id": 0}))
    if not before: raise HTTPException(404, "Delegation not found")
    await db.delegations.update_one({"delegation_id": delegation_id}, {"$set": {"status": "Revoked", "revoked_at": now_iso()}})
    await log_event(user, "delegation revoked", "delegation", delegation_id, before=before)
    return {"ok": True}

# --- Bulk CSV import ---
@api.post("/admin/imports/{kind}")
async def bulk_import(kind: str, request: Request, user=Depends(require_permission("admin"))):
    if kind not in {"assets", "students"}: raise HTTPException(400, "kind must be 'assets' or 'students'")
    import csv, io as _io
    body = (await request.body()).decode("utf-8", errors="replace")
    if not body.strip(): raise HTTPException(400, "Empty CSV")
    reader = csv.DictReader(_io.StringIO(body))
    if reader.fieldnames is None: raise HTTPException(400, "CSV missing header row")
    headers = [h.strip().lower() for h in (reader.fieldnames or [])]
    rows_out = []; created = 0; skipped = 0
    if kind == "assets":
        required = {"name", "category", "location", "department"}
        if not required.issubset(headers): raise HTTPException(400, f"CSV needs columns: {sorted(required)}")
        for i, raw in enumerate(reader, start=2):
            row = {k.strip().lower(): (v or "").strip() for k, v in raw.items()}
            missing = [c for c in required if not row.get(c)]
            if missing: rows_out.append({"row": i, "status": "error", "message": f"missing: {', '.join(missing)}"}); skipped += 1; continue
            asset = {"asset_id": f"ast_{uuid.uuid4().hex[:10]}", "name": row["name"], "category": row["category"], "location": row["location"], "department": row["department"], "status": row.get("status") or "Available", "tag": row.get("tag") or f"AF-{datetime.now().year}-{secrets.randbelow(9000)+1000}", "serial": row.get("serial") or f"SN-{uuid.uuid4().hex[:8].upper()}", "bookable": (row.get("bookable", "").lower() in {"1", "true", "yes"}), "updated_at": now_iso(), "created_at": now_iso()}
            await db.assets.insert_one(asset)
            rows_out.append({"row": i, "status": "created", "asset_id": asset["asset_id"], "name": asset["name"]}); created += 1
    else:
        required = {"name", "email", "roll_number", "department"}
        if not required.issubset(headers): raise HTTPException(400, f"CSV needs columns: {sorted(required)}")
        for i, raw in enumerate(reader, start=2):
            row = {k.strip().lower(): (v or "").strip() for k, v in raw.items()}
            missing = [c for c in required if not row.get(c)]
            if missing: rows_out.append({"row": i, "status": "error", "message": f"missing: {', '.join(missing)}"}); skipped += 1; continue
            if "@" not in row["email"] or "." not in row["email"]: rows_out.append({"row": i, "status": "error", "message": "invalid email"}); skipped += 1; continue
            if await db.users.find_one({"email": row["email"]}, {"_id": 0}):
                rows_out.append({"row": i, "status": "skipped", "message": "email already exists"}); skipped += 1; continue
            student = {"user_id": f"user_{uuid.uuid4().hex[:12]}", "name": row["name"], "email": row["email"], "role": "Student", "department": row["department"], "status": "Pending", "picture": "", "created_at": now_iso(), "roll_number": row["roll_number"], "password_hash": bcrypt.hashpw(secrets.token_urlsafe(12).encode(), bcrypt.gensalt()).decode()}
            await db.users.insert_one(student)
            rows_out.append({"row": i, "status": "created", "user_id": student["user_id"], "name": student["name"]}); created += 1
    await log_event(user, f"bulk imported {kind}", "import", kind, metadata={"created": created, "skipped": skipped})
    return {"kind": kind, "created": created, "skipped": skipped, "rows": rows_out}

# --- Audit PDF with photo grid ---
@api.get("/audits/{audit_id}/pdf")
async def audit_pdf(audit_id: str, user=Depends(require_permission("audit"))):
    from fastapi.responses import StreamingResponse
    import io, urllib.request, tempfile
    audit = await db.audits.find_one({"audit_id": audit_id}, {"_id": 0})
    if not audit: raise HTTPException(404, "Audit not found")
    brand = {**BRANDING_DEFAULT, **{k: v for k, v in ((await db.branding.find_one({"_id": "singleton"})) or {}).items() if k != "_id"}}
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, PageBreak
    try: accent = colors.HexColor(brand.get("accent_color") or "#171717")
    except Exception: accent = colors.HexColor("#171717")
    buf = io.BytesIO(); doc = SimpleDocTemplate(buf, pagesize=A4, title=f"Audit {audit_id}")
    styles = getSampleStyleSheet()
    story = [Paragraph(brand.get("accreditation_body") or "AUDIT REPORT", ParagraphStyle("eb", parent=styles["Normal"], textColor=colors.HexColor("#8f8f8f"), fontSize=10)), Paragraph(brand.get("institution_name") or "AssetFlow Campus", ParagraphStyle("t", parent=styles["Title"], textColor=accent, fontSize=26, spaceAfter=6)), Paragraph(f"{audit['department']} · {audit['period']}", styles["Heading2"]), Paragraph(f"Cycle ID: {audit_id} · Status: {audit.get('status')} · Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}", styles["Normal"]), Spacer(1, 18)]
    verify_rows = [["Asset", "Tag", "Expected location", "Verification", "Note"]] + [[i["name"], i["tag"], i["expected_location"], i.get("verification", "Pending"), i.get("note", "")] for i in audit.get("items", [])]
    t = Table(verify_rows, colWidths=[130, 80, 130, 70, 90], repeatRows=1)
    t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),accent),("TEXTCOLOR",(0,0),(-1,0),colors.white),("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),("FONTSIZE",(0,0),(-1,-1),9),("GRID",(0,0),(-1,-1),0.3,colors.HexColor("#ebebeb")),("VALIGN",(0,0),(-1,-1),"MIDDLE"),("TOPPADDING",(0,0),(-1,-1),5),("BOTTOMPADDING",(0,0),(-1,-1),5)]))
    story.append(t)
    photo_items = [(i, p) for i in audit.get("items", []) for p in (i.get("photos") or [])]
    if photo_items:
        story.append(PageBreak())
        story.append(Paragraph("Evidence photos", styles["Heading2"]))
        story.append(Spacer(1, 10))
        cells = []; row = []
        for it, ph in photo_items:
            try:
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".img")
                with urllib.request.urlopen(ph["url"], timeout=6) as r: tmp.write(r.read())
                tmp.close()
                cell = [Image(tmp.name, width=52*mm, height=52*mm, kind="proportional"), Spacer(1, 4), Paragraph(f"<b>{it['name']}</b>", styles["Normal"]), Paragraph(f"{it['tag']} · {it.get('verification','')}", ParagraphStyle('c', parent=styles["Normal"], fontSize=8, textColor=colors.HexColor("#8f8f8f")))]
                row.append(cell)
                if len(row) == 3: cells.append(row); row = []
            except Exception: pass
        if row: row += [""] * (3 - len(row)); cells.append(row)
        if cells:
            grid = Table(cells, colWidths=[60*mm, 60*mm, 60*mm])
            grid.setStyle(TableStyle([("VALIGN",(0,0),(-1,-1),"TOP"),("LEFTPADDING",(0,0),(-1,-1),4),("RIGHTPADDING",(0,0),(-1,-1),4),("TOPPADDING",(0,0),(-1,-1),6),("BOTTOMPADDING",(0,0),(-1,-1),6)]))
            story.append(grid)
    story.append(Spacer(1, 18))
    story.append(Paragraph(brand.get("footer") or BRANDING_DEFAULT["footer"], styles["Italic"]))
    doc.build(story); buf.seek(0)
    await log_event(user, "audit report downloaded", "audit", audit_id, metadata={"format": "pdf", "photo_count": len(photo_items)})
    return StreamingResponse(iter([buf.getvalue()]), media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="assetflow_audit_{audit_id}.pdf"'})

async def seed():
    if await db.assets.count_documents({}): return
    samples=[("Oscilloscope TBS1202","Lab Equipment","Electronics Lab","Computer Science","Allocated"),("Epson Projector EB-X06","IT Equipment","Seminar Hall 2","Administration","Available"),("CNC Milling Unit","Workshop Machinery","Mechanical Workshop","Mechanical","Under Maintenance"),("3D Printer Pro","Lab Equipment","Innovation Lab","Computer Science","Available"),("Canon EOS 90D","Media Equipment","Media Room","Administration","Allocated"),("Sports Kit — Cricket","Sports Gear","Sports Complex","Sports","Available")]
    for i,(name,cat,loc,dept,status) in enumerate(samples): await db.assets.insert_one({"asset_id":f"ast_seed_{i}","tag":f"AF-2025-{1000+i}","name":name,"category":cat,"location":loc,"department":dept,"status":status,"serial":f"SN-{uuid.uuid4().hex[:8].upper()}","bookable":i in [1,3,5],"holder":"Dr. Maya Iyer" if status=="Allocated" else None,"updated_at":now_iso(),"created_at":now_iso()})
    await db.maintenance.insert_one({"request_id":"mnt_seed_01","asset_id":"ast_seed_2","description":"Spindle vibration during calibration","priority":"High","raised_by":"Arjun Menon","status":"In progress","created_at":now_iso()})
    await db.activity.insert_many([{"event_id":f"evt_seed_{i}","actor_id":"system","actor":"AssetFlow System","action":action,"entity_type":"asset","entity_id":f"ast_seed_{i}","before":None,"after":None,"metadata":{},"timestamp":(datetime.now(timezone.utc)-timedelta(hours=i*3)).isoformat()} for i,action in enumerate(["asset audit completed","maintenance request raised","asset checked out","booking created","asset registered"])])
    email="demo@assetflow.edu"
    if not await db.users.find_one({"email":email}):
        user={"user_id":"user_demo_assetflow","name":"Maya Iyer","email":email,"role":"Asset Manager","department":"Computer Science","status":"Active","picture":"","created_at":now_iso(),"password_hash":bcrypt.hashpw(b"Campus123!",bcrypt.gensalt()).decode()}; await db.users.insert_one(user)
    if not await db.users.find_one({"email": "admin@assetflow.edu"}):
        admin={"user_id":"user_demo_admin","name":"Rohan Kapoor","email":"admin@assetflow.edu","role":"Admin","department":"Administration","status":"Active","picture":"","created_at":now_iso(),"password_hash":bcrypt.hashpw(b"Admin123!",bcrypt.gensalt()).decode()}; await db.users.insert_one(admin)
    if not await db.departments.count_documents({}):
        await db.departments.insert_many([{ "department_id": f"dept_seed_{i}", "name": name, "type": "academic", "head": "", "status": "Active", "created_at": now_iso() } for i, name in enumerate(["Computer Science", "Mechanical", "Civil", "Administration", "Sports"])])
    if not await db.categories.count_documents({}):
        await db.categories.insert_many([{ "category_id": f"cat_seed_{i}", "name": name, "example_items": examples, "warranty_tracked": True, "amc_tracked": False, "created_at": now_iso() } for i, (name, examples) in enumerate([("IT Equipment", "Projectors, cameras, laptops"), ("Lab Equipment", "Oscilloscopes, 3D printers"), ("Sports Gear", "Bats, nets, jerseys")])])
    if not await db.nodues.count_documents({}):
        await db.nodues.insert_many([{ "student_id": f"student_seed_{i}", "student_name": name, "roll_number": roll, "overall_status": status, "department_statuses": [{"department": d, "status": "Cleared" if status == "Cleared" else ("Pending" if d == "Library" else "Cleared"), "note": ""} for d in ["Library", "Hostel", "Sports"]] } for i, (name, roll, status) in enumerate([("Ananya Rao", "CSE21A004", "In progress"), ("Vikram Shah", "ME22B018", "Cleared"), ("Sara Thomas", "CE21C011", "In progress")])])

async def ensure_supporting_seed():
    if not await db.users.find_one({"email": "admin@assetflow.edu"}):
        await db.users.insert_one({"user_id":"user_demo_admin","name":"Rohan Kapoor","email":"admin@assetflow.edu","role":"Admin","department":"Administration","status":"Active","picture":"","created_at":now_iso(),"password_hash":bcrypt.hashpw(b"Admin123!",bcrypt.gensalt()).decode()})
    if not await db.departments.count_documents({}):
        await db.departments.insert_many([{ "department_id": f"dept_seed_{i}", "name": name, "type": "academic", "head": "", "status": "Active", "created_at": now_iso() } for i, name in enumerate(["Computer Science", "Mechanical", "Civil", "Administration", "Sports"])])
    if not await db.categories.count_documents({}):
        await db.categories.insert_many([{ "category_id": f"cat_seed_{i}", "name": name, "example_items": examples, "warranty_tracked": True, "amc_tracked": False, "created_at": now_iso() } for i, (name, examples) in enumerate([("IT Equipment", "Projectors, cameras, laptops"), ("Lab Equipment", "Oscilloscopes, 3D printers"), ("Sports Gear", "Bats, nets, jerseys")])])
    if not await db.nodues.count_documents({}):
        await db.nodues.insert_many([{ "student_id": f"student_seed_{i}", "student_name": name, "roll_number": roll, "overall_status": status, "department_statuses": [{"department": d, "status": "Cleared" if status == "Cleared" else ("Pending" if d == "Library" else "Cleared"), "note": ""} for d in ["Library", "Hostel", "Sports"]] } for i, (name, roll, status) in enumerate([("Ananya Rao", "CSE21A004", "In progress"), ("Vikram Shah", "ME22B018", "Cleared"), ("Sara Thomas", "CE21C011", "In progress")])])

async def ensure_demo_data():
    """Idempotent rich demo/temporary data so every feature is testable. Uses stable IDs + upserts."""
    try:
        # --- Bookable resources (rooms, projector, vehicle, laptop) ---
        resources = [
            ("ast_demo_laptop1", "AF-0006", "Dell Latitude Laptop", "IT Equipment", "HQ floor 3", "Computer Science"),
            ("ast_demo_room1", "AF-2025-2001", "Seminar Hall A", "Room", "Academic Block · Floor 2", "Administration"),
            ("ast_demo_room2", "AF-2025-2002", "Conference Room B", "Room", "Admin Block · Floor 1", "Administration"),
            ("ast_demo_proj1", "AF-2025-2003", "Epson Projector EB-X06", "Projector", "AV Store", "Administration"),
            ("ast_demo_vehicle1", "AF-2025-2004", "College Bus (32-seater)", "Vehicle", "Transport Bay", "Administration"),
        ]
        for aid, tag, name, cat, loc, dept in resources:
            await db.assets.update_one({"asset_id": aid}, {"$set": {"asset_id": aid, "tag": tag, "name": name, "category": cat, "location": loc, "department": dept, "status": "Available", "bookable": True, "serial": f"SN-{aid[-6:].upper()}", "updated_at": now_iso()}, "$setOnInsert": {"created_at": now_iso()}}, upsert=True)

        # --- Demo users with known passwords for role testing ---
        pwd = bcrypt.hashpw(b"Campus123!", bcrypt.gensalt()).decode()
        demo_users = [
            ("user_demo_priya", "Priya Ramesh", "priya@assetflow.edu", "HOD", "Computer Science", "Active"),
            ("user_demo_arjun", "Arjun Menon", "arjun@assetflow.edu", "Employee", "Mechanical", "Active"),
            ("user_demo_ananya", "Ananya Rao", "ananya@assetflow.edu", "Student", "Computer Science", "Active"),
            ("user_demo_vikram", "Vikram Shah", "vikram@assetflow.edu", "Student", "Mechanical", "Pending"),
        ]
        for uid, name, email, role, dept, status in demo_users:
            await db.users.update_one({"email": email}, {"$set": {"user_id": uid, "name": name, "email": email, "role": role, "department": dept, "status": status, "password_hash": pwd, "picture": ""}, "$setOnInsert": {"created_at": now_iso()}}, upsert=True)

        # --- Bookings across the next 7 days (upsert keeps them current & idempotent) ---
        today = datetime.now(timezone.utc).date()
        demo_bookings = [
            ("laptop1", "ast_demo_laptop1", "Dell Latitude Laptop", "HQ floor 3", "IT Equipment", 0, "09:00", "10:00", "Team retrospective", "Sprint retro", "Computer Science", 8, "Priya Ramesh", "user_demo_priya"),
            ("room1", "ast_demo_room1", "Seminar Hall A", "Academic Block · Floor 2", "Room", 1, "11:00", "13:00", "Guest lecture — AI in Industry", "Guest Lecture", "Computer Science", 120, "Priya Ramesh", "user_demo_priya"),
            ("room2", "ast_demo_room2", "Conference Room B", "Admin Block · Floor 1", "Room", 3, "15:00", "16:30", "Department review meeting", "Dept Review", "Administration", 15, "Rohan Kapoor", "user_demo_admin"),
            ("proj1", "ast_demo_proj1", "Epson Projector EB-X06", "AV Store", "Projector", 4, "10:00", "12:00", "NBA documentation shoot", "Accreditation", "Administration", 5, "Maya Iyer", "user_demo_assetflow"),
            ("bus1", "ast_demo_vehicle1", "College Bus (32-seater)", "Transport Bay", "Vehicle", 6, "07:00", "18:00", "Industrial visit — Foundry", "Industrial Visit", "Mechanical", 32, "Arjun Menon", "user_demo_arjun"),
        ]
        for key, rid, rname, loc, cat, offset, st, et, purpose, title, dept, att, by, by_id in demo_bookings:
            d = (today + timedelta(days=offset)).isoformat()
            await db.bookings.update_one({"booking_id": f"book_demo_{key}"}, {"$set": {"booking_id": f"book_demo_{key}", "resource_id": rid, "resource_name": rname, "location": loc, "category": cat, "date": d, "start_time": st, "end_time": et, "purpose": purpose, "event_title": title, "department": dept, "attendees": att, "contact": "", "requested_by": by, "requested_by_id": by_id, "status": "Confirmed"}, "$setOnInsert": {"created_at": now_iso()}}, upsert=True)

        # --- Maintenance across all stages ---
        maints = [
            ("mnt_demo_open", "ast_demo_proj1", "Projector lamp flickering during lectures", "Medium", "Priya Ramesh", "user_demo_priya", "Open", None),
            ("mnt_demo_prog", "ast_seed_0", "Oscilloscope probe calibration drift", "High", "Arjun Menon", "user_demo_arjun", "In progress", None),
            ("mnt_demo_res", "ast_demo_room1", "AC not cooling in Seminar Hall A", "Low", "Maya Iyer", "user_demo_assetflow", "Resolved", (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()),
        ]
        for rid, aid, desc, prio, by, by_id, status, resolved in maints:
            setd = {"request_id": rid, "asset_id": aid, "description": desc, "priority": prio, "raised_by": by, "raised_by_id": by_id, "status": status}
            if resolved: setd["resolved_at"] = resolved
            await db.maintenance.update_one({"request_id": rid}, {"$set": setd, "$setOnInsert": {"created_at": now_iso(), "photos": []}}, upsert=True)

        # --- One closed audit with fixed items (so PDF/photo grid is testable) ---
        if not await db.audits.find_one({"audit_id": "audit_demo_closed"}):
            cs_assets = [clean(x) for x in await db.assets.find({"department": "Computer Science"}, {"_id": 0}).to_list(50)]
            items = [{"asset_id": x["asset_id"], "tag": x["tag"], "name": x["name"], "expected_location": x["location"], "verification": "Verified", "note": "", "photos": []} for x in cs_assets]
            await db.audits.insert_one({"audit_id": "audit_demo_closed", "department": "Computer Science", "period": "July 2026", "auditors": ["Maya Iyer"], "status": "Closed", "created_at": now_iso(), "closed_at": now_iso(), "items": items})

        # --- Extra no-dues records ---
        for i, (sid, name, roll, status) in enumerate([("student_demo_1", "Neha Gupta", "CSE21A012", "In progress"), ("student_demo_2", "Karan Patel", "ME22B033", "Cleared")]):
            await db.nodues.update_one({"student_id": sid}, {"$setOnInsert": {"student_id": sid, "student_name": name, "roll_number": roll, "overall_status": status, "department_statuses": [{"department": d, "status": ("Cleared" if status == "Cleared" or d != "Library" else "Pending"), "note": ""} for d in ["Library", "Hostel", "Sports"]]}}, upsert=True)
    except Exception as e:
        logger.warning(f"ensure_demo_data skipped: {e}")

@app.on_event("startup")
async def startup():
    await seed()
    await ensure_supporting_seed()
    await ensure_demo_data()
@app.on_event("shutdown")
async def shutdown(): client.close()
app.include_router(api)
app.add_middleware(CORSMiddleware, allow_credentials=True, allow_origins=os.environ.get("CORS_ORIGINS","*").split(","), allow_methods=["*"], allow_headers=["*"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)