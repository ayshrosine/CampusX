from fastapi import FastAPI, APIRouter, HTTPException, Request, Response, Depends
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field, EmailStr
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Optional, List
import os, uuid, secrets, bcrypt, logging
from bson import ObjectId

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")
client = AsyncIOMotorClient(os.environ["MONGO_URL"])
db = client[os.environ["DB_NAME"]]
app = FastAPI(title="AssetFlow Campus API")
api = APIRouter(prefix="/api")
logger = logging.getLogger("assetflow")

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

class MaintenanceStatus(BaseModel):
    status: str

class DepartmentCreate(BaseModel):
    name: str
    type: str = "academic"
    head: str = ""

class CategoryCreate(BaseModel):
    name: str
    example_items: str = ""
    warranty_tracked: bool = False
    amc_tracked: bool = False

class RoleChange(BaseModel):
    role: str
    status: str = "Active"

class BookingCreate(BaseModel):
    resource_id: str
    date: str
    start_time: str
    end_time: str
    purpose: str

class AuditCreate(BaseModel):
    department: str
    period: str
    auditors: List[str] = []

class AuditItemUpdate(BaseModel):
    verification: str
    note: str = ""

class NoDuesUpdate(BaseModel):
    status: str
    note: str = ""

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

@api.post("/auth/session")
async def oauth_session(request: Request, response: Response):
    session_id = request.headers.get("X-Session-ID")
    if not session_id: raise HTTPException(400, "Missing session id")
    import requests
    remote = requests.get("https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data", headers={"X-Session-ID": session_id}, timeout=15)
    if remote.status_code != 200: raise HTTPException(401, "Google session could not be verified")
    data = remote.json(); user = await db.users.find_one({"email": data["email"]}, {"_id": 0})
    if not user:
        user = {"user_id": f"user_{uuid.uuid4().hex[:12]}", "name": data.get("name", data["email"].split("@")[0]), "email": data["email"], "role": "Student", "department": "Computer Science", "status": "Pending", "picture": data.get("picture", ""), "created_at": now_iso()}
        await db.users.insert_one(user)
        await log_event(user, "account created with Google", "user", user["user_id"], after={"email": user["email"], "role": user["role"]})
    token = await create_session(user["user_id"])
    return session_response(Response(content=__import__("json").dumps({k:v for k,v in user.items() if k != "password_hash"}), media_type="application/json"), token)

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
async def maintenance(user=Depends(current_user)): return [clean(x) for x in await db.maintenance.find({}, {"_id":0}).sort("created_at",-1).to_list(100)]

@api.post("/maintenance")
async def create_maintenance(payload: MaintenanceCreate, user=Depends(current_user)):
    item={**payload.model_dump(),"request_id":f"mnt_{uuid.uuid4().hex[:10]}","raised_by":user["name"],"status":"Pending","created_at":now_iso()}; await db.maintenance.insert_one(item); await log_event(user,"maintenance request raised","maintenance",item["request_id"],after=item); return clean(item)

@api.patch("/maintenance/{request_id}")
async def update_maintenance(request_id: str, payload: MaintenanceStatus, user=Depends(current_user)):
    before=clean(await db.maintenance.find_one({"request_id":request_id},{"_id":0}))
    if not before: raise HTTPException(404,"Request not found")
    await db.maintenance.update_one({"request_id":request_id},{"$set":{"status":payload.status}}); after={**before,"status":payload.status}; await log_event(user,"maintenance status changed","maintenance",request_id,before=before,after=after); return clean(after)

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

@app.on_event("startup")
async def startup():
    await seed()
    await ensure_supporting_seed()
@app.on_event("shutdown")
async def shutdown(): client.close()
app.include_router(api)
app.add_middleware(CORSMiddleware, allow_credentials=True, allow_origins=os.environ.get("CORS_ORIGINS","*").split(","), allow_methods=["*"], allow_headers=["*"])