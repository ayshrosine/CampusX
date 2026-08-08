#!/usr/bin/env python3
"""Seed and clean focused UI data for iteration 5 browser verification."""
import argparse
import datetime as dt
import json
import re
import time
import uuid
from pathlib import Path

import bcrypt
import requests
from pymongo import MongoClient

ROOT = Path("/app")
API = "https://complete-coverage-3.preview.emergentagent.com/api"
STATE_PATH = ROOT / "test_reports" / "bug_verification_5_ui_seed.json"
DEFAULT_BRAND = {
    "institution_name": "AssetFlow Campus",
    "tagline": "Every asset. Accountable.",
    "accreditation_body": "NAAC / NBA",
    "footer": "",
    "accent_color": "#171717",
    "logo_url": "",
}


def parse_env(path: Path):
    out = {}
    for line in path.read_text().splitlines():
        if line and "=" in line and not line.strip().startswith("#"):
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def db_client():
    env = parse_env(ROOT / "backend" / ".env")
    client = MongoClient(env["MONGO_URL"], serverSelectionTimeoutMS=10000)
    return client, client[env["DB_NAME"]]


def login_admin():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": "admin@assetflow.edu", "password": "Admin123!"}, timeout=20)
    r.raise_for_status()
    return s


def public_id_from_cloudinary_url(url: str):
    if not url:
        return ""
    m = re.search(r"/image/upload/(?:v\d+/)?(.+?)(?:\.[a-zA-Z0-9]+)?(?:\?.*)?$", url)
    return m.group(1) if m else ""


def setup():
    client, db = db_client()
    admin = login_admin()
    try:
        # Remove old photos from the seed maintenance card through the API so Cloudinary is also cleaned up.
        maint = admin.get(f"{API}/maintenance", timeout=20).json()
        for item in maint:
            if item.get("request_id") == "mnt_seed_01":
                for p in item.get("photos", []):
                    admin.delete(f"{API}/maintenance/mnt_seed_01/photos/{requests.utils.quote(p['public_id'], safe='')}", timeout=30)
        db.maintenance.update_one({"request_id": "mnt_seed_01"}, {"$set": {"photos": [], "status": "In progress", "description": "Spindle vibration during calibration"}})

        stamp = int(time.time())
        pending_email = f"bugverify5_pending_{stamp}@assetflow.edu"
        pending_user_id = f"user_bugverify5_{uuid.uuid4().hex[:8]}"
        db.users.insert_one({
            "user_id": pending_user_id,
            "name": "Bug Verify Pending",
            "email": pending_email,
            "role": "Student",
            "department": "Computer Science",
            "status": "Pending",
            "picture": "",
            "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "password_hash": bcrypt.hashpw(b"Campus123!", bcrypt.gensalt()).decode(),
        })

        tomorrow = (dt.datetime.now(dt.timezone.utc).date() + dt.timedelta(days=1)).isoformat()
        booking = admin.post(f"{API}/bookings", json={
            "resource_id": f"BugVerify Room {stamp}",
            "date": tomorrow,
            "start_time": "07:00",
            "end_time": "07:30",
            "purpose": "Digest row verification",
        }, timeout=20).json()

        audit = admin.post(f"{API}/audits", json={
            "department": "Computer Science",
            "period": f"BugVerify UI {stamp}",
            "auditors": ["QA"],
        }, timeout=20).json()

        state = {"booking_id": booking.get("booking_id"), "audit_id": audit.get("audit_id"), "pending_email": pending_email, "pending_user_id": pending_user_id, "stamp": stamp}
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        STATE_PATH.write_text(json.dumps(state, indent=2))
        print(json.dumps(state, indent=2))
    finally:
        client.close()


def cleanup():
    state = json.loads(STATE_PATH.read_text()) if STATE_PATH.exists() else {}
    client, db = db_client()
    try:
        if state.get("booking_id"):
            db.bookings.delete_many({"booking_id": state["booking_id"]})
        if state.get("audit_id"):
            db.audits.delete_many({"audit_id": state["audit_id"]})
        if state.get("pending_email"):
            user = db.users.find_one({"email": state["pending_email"]}) or {}
            if user.get("user_id"):
                db.user_sessions.delete_many({"user_id": user["user_id"]})
            db.users.delete_many({"email": state["pending_email"]})
        # Clean any photo left by the browser maintenance test.
        admin = login_admin()
        maint = admin.get(f"{API}/maintenance", timeout=20).json()
        for item in maint:
            if item.get("request_id") == "mnt_seed_01":
                for p in item.get("photos", []):
                    admin.delete(f"{API}/maintenance/mnt_seed_01/photos/{requests.utils.quote(p['public_id'], safe='')}", timeout=30)
        db.maintenance.update_one({"request_id": "mnt_seed_01"}, {"$set": {"photos": []}})

        # Destroy any branding upload left from the UI test, then restore requested defaults.
        brand = db.branding.find_one({"_id": "singleton"}) or {}
        pub = public_id_from_cloudinary_url(brand.get("logo_url", ""))
        if pub:
            try:
                import cloudinary
                import cloudinary.uploader
                env = parse_env(ROOT / "backend" / ".env")
                cloudinary.config(cloud_name=env.get("CLOUDINARY_CLOUD_NAME"), api_key=env.get("CLOUDINARY_API_KEY"), api_secret=env.get("CLOUDINARY_API_SECRET"), secure=True)
                cloudinary.uploader.destroy(pub, invalidate=True)
            except Exception as exc:
                print(f"WARN: unable to destroy branding Cloudinary asset {pub}: {exc}")
        db.branding.update_one({"_id": "singleton"}, {"$set": {**DEFAULT_BRAND, "updated_at": dt.datetime.now(dt.timezone.utc).isoformat(), "updated_by": "Bug Verification"}}, upsert=True)
        print("cleanup complete")
    finally:
        client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--cleanup", action="store_true")
    args = parser.parse_args()
    cleanup() if args.cleanup else setup()