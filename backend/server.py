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
async def reports(user=Depends(current_user)):
    assets=[clean(x) for x in await db.assets.find({}, {"_id":0}).to_list(500)]; by_dept={}
    for a in assets: by_dept.setdefault(a["department"],{"name":a["department"],"total":0,"allocated":0}); by_dept[a["department"]]["total"]+=1; by_dept[a["department"]]["allocated"]+=a["status"]=="Allocated"
    return {"departments":list(by_dept.values()),"status_counts":{s:sum(a["status"]==s for a in assets) for s in ["Available","Allocated","Under Maintenance","Lost","Retired"]},"total":len(assets)}

async def seed():
    if await db.assets.count_documents({}): return
    samples=[("Oscilloscope TBS1202","Lab Equipment","Electronics Lab","Computer Science","Allocated"),("Epson Projector EB-X06","IT Equipment","Seminar Hall 2","Administration","Available"),("CNC Milling Unit","Workshop Machinery","Mechanical Workshop","Mechanical","Under Maintenance"),("3D Printer Pro","Lab Equipment","Innovation Lab","Computer Science","Available"),("Canon EOS 90D","Media Equipment","Media Room","Administration","Allocated"),("Sports Kit — Cricket","Sports Gear","Sports Complex","Sports","Available")]
    for i,(name,cat,loc,dept,status) in enumerate(samples): await db.assets.insert_one({"asset_id":f"ast_seed_{i}","tag":f"AF-2025-{1000+i}","name":name,"category":cat,"location":loc,"department":dept,"status":status,"serial":f"SN-{uuid.uuid4().hex[:8].upper()}","bookable":i in [1,3,5],"holder":"Dr. Maya Iyer" if status=="Allocated" else None,"updated_at":now_iso(),"created_at":now_iso()})
    await db.maintenance.insert_one({"request_id":"mnt_seed_01","asset_id":"ast_seed_2","description":"Spindle vibration during calibration","priority":"High","raised_by":"Arjun Menon","status":"In progress","created_at":now_iso()})
    await db.activity.insert_many([{"event_id":f"evt_seed_{i}","actor_id":"system","actor":"AssetFlow System","action":action,"entity_type":"asset","entity_id":f"ast_seed_{i}","before":None,"after":None,"metadata":{},"timestamp":(datetime.now(timezone.utc)-timedelta(hours=i*3)).isoformat()} for i,action in enumerate(["asset audit completed","maintenance request raised","asset checked out","booking created","asset registered"])])
    email="demo@assetflow.edu"
    if not await db.users.find_one({"email":email}):
        user={"user_id":"user_demo_assetflow","name":"Maya Iyer","email":email,"role":"Asset Manager","department":"Computer Science","status":"Active","picture":"","created_at":now_iso(),"password_hash":bcrypt.hashpw(b"Campus123!",bcrypt.gensalt()).decode()}; await db.users.insert_one(user)

@app.on_event("startup")
async def startup(): await seed()
@app.on_event("shutdown")
async def shutdown(): client.close()
app.include_router(api)
app.add_middleware(CORSMiddleware, allow_credentials=True, allow_origins=os.environ.get("CORS_ORIGINS","*").split(","), allow_methods=["*"], allow_headers=["*"])