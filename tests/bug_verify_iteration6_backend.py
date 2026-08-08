#!/usr/bin/env python3
"""Focused backend/API verification for iteration 6 AssetFlow features.

This script intentionally creates only TEST_/bug-verify data and cleans it up at
the end. It verifies the four user-visible feature areas requested by the main
agent: push notifications, bulk CSV import, delegation slots, and audit PDFs.
"""

import asyncio
import base64
import importlib
import io
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
from PIL import Image as PILImage
from pymongo import MongoClient
from PyPDF2 import PdfReader


ROOT = Path("/app")
API_BASE = "https://complete-coverage-3.preview.emergentagent.com/api"
FRONTEND_BASE = "https://complete-coverage-3.preview.emergentagent.com"
RUN_ID = f"TEST_ITER6_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
ADMIN_EMAIL = "admin@assetflow.edu"
ADMIN_PASSWORD = "Admin123!"
DEMO_EMAIL = "demo@assetflow.edu"
DEMO_PASSWORD = "Campus123!"


def load_backend_env():
    env_path = ROOT / "backend" / ".env"
    out = {}
    for line in env_path.read_text().splitlines():
        if not line or line.strip().startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        out[key.strip()] = val.strip().strip('"').strip("'")
    return out


ENV = load_backend_env()
mongo = MongoClient(ENV["MONGO_URL"])
db = mongo[ENV["DB_NAME"]]


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


async def login(email, password):
    client = httpx.AsyncClient(base_url=API_BASE, timeout=45.0, follow_redirects=True)
    res = await client.post("/auth/login", json={"email": email, "password": password})
    assert_true(res.status_code == 200, f"login failed for {email}: {res.status_code} {res.text}")
    return client, res.json()


def make_data_uri_png():
    img = PILImage.new("RGB", (240, 160), color=(65, 105, 225))
    # Draw simple color blocks without needing ImageDraw fonts.
    for x in range(0, 240, 12):
        for y in range(0, 160, 12):
            if (x // 12 + y // 12) % 2 == 0:
                for xx in range(x, min(x + 12, 240)):
                    for yy in range(y, min(y + 12, 160)):
                        img.putpixel((xx, yy), (230, 240, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def extract_pdf_text(pdf_bytes):
    reader = PdfReader(io.BytesIO(pdf_bytes))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    return text


async def test_push_subscription_and_sw(admin_client, admin_user):
    results = {}
    key_res = await admin_client.get("/push/public-key")
    assert_true(key_res.status_code == 200, f"public key status {key_res.status_code}")
    vapid_key = key_res.json().get("key", "")
    assert_true(len(vapid_key) > 20, "VAPID public key is empty/too short")
    results["public_key_length"] = len(vapid_key)

    sw_res = await httpx.AsyncClient(timeout=30.0).get(f"{FRONTEND_BASE}/sw.js")
    assert_true(sw_res.status_code == 200, f"sw.js status {sw_res.status_code}")
    ctype = sw_res.headers.get("content-type", "")
    assert_true("javascript" in ctype or "text/plain" in ctype, f"unexpected sw.js content-type {ctype}")
    assert_true("addEventListener(\"push\"" in sw_res.text or "addEventListener('push'" in sw_res.text, "sw.js lacks push listener")
    results["sw_content_type"] = ctype

    endpoint = f"https://example.com/fake-push/{RUN_ID}"
    payload = {"endpoint": endpoint, "keys": {"p256dh": "fake-p256dh-key", "auth": "fake-auth-key"}}
    sub_res = await admin_client.post("/push/subscribe", json=payload)
    assert_true(sub_res.status_code == 200, f"subscribe status {sub_res.status_code}: {sub_res.text}")
    sub_doc = db.push_subs.find_one({"endpoint": endpoint}, {"_id": 0})
    assert_true(sub_doc is not None, "push subscription was not persisted")
    assert_true(sub_doc.get("user_id") == admin_user["user_id"], "push subscription not tied to caller")
    assert_true(sub_doc.get("role") == admin_user["role"], "push subscription role not saved")

    unsub_res = await admin_client.post("/push/unsubscribe", json=payload)
    assert_true(unsub_res.status_code == 200, f"unsubscribe status {unsub_res.status_code}: {unsub_res.text}")
    assert_true(db.push_subs.find_one({"endpoint": endpoint}) is None, "push unsubscribe did not delete row")
    results["subscribe_upsert_and_delete"] = True
    return results


async def test_push_send_code_path(admin_client):
    """Verify High invokes send_push_to_role and Medium does not.

    Uses a monkeypatched backend function for deterministic proof of invocation,
    plus an API-created High request to verify the deployed endpoint accepts the
    user-visible workflow and exposes it in the notifications feed.
    """
    sys.path.insert(0, str(ROOT / "backend"))
    server = importlib.import_module("server")
    calls = []

    async def fake_send(roles, title, body, url="/dashboard"):
        calls.append({"roles": roles, "title": title, "body": body, "url": url})
        return 1

    original = server.send_push_to_role
    server.send_push_to_role = fake_send
    try:
        user = db.users.find_one({"email": DEMO_EMAIL}, {"_id": 0, "password_hash": 0})
        high_payload = server.MaintenanceCreate(asset_id="ast_seed_2", description=f"{RUN_ID} direct high push", priority="High")
        med_payload = server.MaintenanceCreate(asset_id="ast_seed_2", description=f"{RUN_ID} direct medium no push", priority="Medium")
        await server.create_maintenance(high_payload, user=user)
        await server.create_maintenance(med_payload, user=user)
    finally:
        server.send_push_to_role = original
        # Do not close the imported module's Mongo client; close() is sync in
        # the installed Motor version and the process exits after this script.

    assert_true(len(calls) == 1, f"expected one push send invocation for High only, got {calls}")
    assert_true(calls[0]["roles"] == ["Admin", "Asset Manager", "HOD"], f"unexpected push roles {calls[0]['roles']}")
    assert_true(calls[0]["url"] == "/maintenance", f"unexpected push url {calls[0]['url']}")

    api_high_desc = f"{RUN_ID} API high notification feed"
    api_low_desc = f"{RUN_ID} API low no notification"
    high_res = await admin_client.post("/maintenance", json={"asset_id": "ast_seed_2", "description": api_high_desc, "priority": "High"})
    low_res = await admin_client.post("/maintenance", json={"asset_id": "ast_seed_2", "description": api_low_desc, "priority": "Low"})
    assert_true(high_res.status_code == 200, f"API high maintenance failed: {high_res.status_code} {high_res.text}")
    assert_true(low_res.status_code == 200, f"API low maintenance failed: {low_res.status_code} {low_res.text}")
    notif = await admin_client.get("/notifications")
    assert_true(notif.status_code == 200, f"notifications failed: {notif.status_code} {notif.text}")
    details = "\n".join(item.get("detail", "") for item in notif.json().get("items", []))
    assert_true(api_high_desc in details, "High priority maintenance did not appear in notification feed")
    assert_true(api_low_desc not in details, "Low priority maintenance appeared in high-priority notification feed")
    return {"push_send_invocations": calls, "api_high_request_id": high_res.json()["request_id"], "api_low_request_id": low_res.json()["request_id"]}


async def test_bulk_import(admin_client, demo_client):
    results = {}
    asset_csv = "name,category,location,department,tag,serial,status,bookable\n" \
                f"{RUN_ID}_Asset_A,IT Equipment,Room 9,Computer Science,{RUN_ID}-TAG-A,{RUN_ID}-SER-A,Available,true\n" \
                f",Lab Equipment,Room 10,Mechanical,{RUN_ID}-TAG-B,{RUN_ID}-SER-B,Available,false\n"
    non_admin_asset = await demo_client.post("/admin/imports/assets", content=asset_csv, headers={"Content-Type": "text/csv"})
    assert_true(non_admin_asset.status_code == 403, f"non-admin asset import expected 403, got {non_admin_asset.status_code}")
    asset_res = await admin_client.post("/admin/imports/assets", content=asset_csv, headers={"Content-Type": "text/csv"})
    assert_true(asset_res.status_code == 200, f"asset import failed: {asset_res.status_code} {asset_res.text}")
    asset_data = asset_res.json()
    assert_true(asset_data["created"] == 1 and asset_data["skipped"] == 1, f"unexpected asset counts {asset_data}")
    assert_true(any(r["status"] == "created" and r.get("asset_id") for r in asset_data["rows"]), "valid asset row not created")
    assert_true(any(r["status"] == "error" and "missing" in r.get("message", "") for r in asset_data["rows"]), "missing required asset row not errored")
    created_asset = db.assets.find_one({"name": f"{RUN_ID}_Asset_A"}, {"_id": 0})
    assert_true(created_asset is not None, "created imported asset not found in DB")
    results["assets"] = asset_data

    student_email = f"{RUN_ID.lower()}@example.edu"
    student_csv = "name,email,roll_number,department\n" \
                  f"{RUN_ID}_Student_A,{student_email},{RUN_ID}ROLL,Computer Science\n" \
                  f"{RUN_ID}_Student_Dupe,{student_email},{RUN_ID}ROLL2,Computer Science\n" \
                  f"{RUN_ID}_Student_Bad,bad-email,{RUN_ID}ROLL3,Mechanical\n" \
                  f",{RUN_ID.lower()}missing@example.edu,{RUN_ID}ROLL4,Sports\n"
    non_admin_student = await demo_client.post("/admin/imports/students", content=student_csv, headers={"Content-Type": "text/csv"})
    assert_true(non_admin_student.status_code == 403, f"non-admin student import expected 403, got {non_admin_student.status_code}")
    student_res = await admin_client.post("/admin/imports/students", content=student_csv, headers={"Content-Type": "text/csv"})
    assert_true(student_res.status_code == 200, f"student import failed: {student_res.status_code} {student_res.text}")
    student_data = student_res.json()
    statuses = [r["status"] for r in student_data["rows"]]
    assert_true(student_data["created"] == 1 and student_data["skipped"] == 3, f"unexpected student counts {student_data}")
    assert_true("created" in statuses and "skipped" in statuses and statuses.count("error") == 2, f"unexpected student row statuses {statuses}")
    created_student = db.users.find_one({"email": student_email}, {"_id": 0, "password_hash": 0})
    assert_true(created_student is not None, "created imported student not found in DB")
    assert_true(created_student.get("role") == "Student" and created_student.get("status") == "Pending", f"imported student role/status wrong: {created_student}")
    results["students"] = student_data
    return results


async def test_delegation(admin_client, demo_client, admin_user, demo_user):
    before = await demo_client.get("/admin/departments")
    assert_true(before.status_code == 403, f"deputy should not access admin endpoint before delegation, got {before.status_code}")

    now = datetime.now(timezone.utc)
    active_payload = {
        "deputy_id": demo_user["user_id"],
        "start_at": (now - timedelta(minutes=2)).isoformat(),
        "end_at": (now + timedelta(hours=2)).isoformat(),
        "note": f"{RUN_ID} active delegation",
    }
    non_admin_res = await demo_client.post("/admin/delegations", json={**active_payload, "note": f"{RUN_ID} nonadmin"})
    assert_true(non_admin_res.status_code == 403, f"non-admin delegation create expected 403, got {non_admin_res.status_code}")

    create_res = await admin_client.post("/admin/delegations", json=active_payload)
    assert_true(create_res.status_code == 200, f"delegation create failed: {create_res.status_code} {create_res.text}")
    delegation = create_res.json()
    assert_true(delegation.get("status") == "Scheduled", f"delegation status wrong: {delegation}")

    self_res = await admin_client.post("/admin/delegations", json={**active_payload, "deputy_id": admin_user["user_id"], "note": f"{RUN_ID} self"})
    assert_true(self_res.status_code == 400, f"self-delegation expected 400, got {self_res.status_code}")

    # Fresh deputy sign-in during active window should be elevated.
    await demo_client.aclose()
    delegated_client, _ = await login(DEMO_EMAIL, DEMO_PASSWORD)
    me_active = await delegated_client.get("/auth/me")
    assert_true(me_active.status_code == 200, f"delegated /auth/me failed: {me_active.status_code} {me_active.text}")
    assert_true(me_active.json().get("role") == "Admin", f"deputy not elevated during active delegation: {me_active.json()}")
    admin_endpoint = await delegated_client.get("/admin/departments")
    assert_true(admin_endpoint.status_code == 200, f"delegated deputy could not access admin endpoint: {admin_endpoint.status_code} {admin_endpoint.text}")

    revoke_res = await admin_client.delete(f"/admin/delegations/{delegation['delegation_id']}")
    assert_true(revoke_res.status_code == 200, f"delegation revoke failed: {revoke_res.status_code} {revoke_res.text}")
    me_revoked = await delegated_client.get("/auth/me")
    assert_true(me_revoked.status_code == 200, f"revoked /auth/me failed: {me_revoked.status_code} {me_revoked.text}")
    assert_true(me_revoked.json().get("role") == demo_user["role"], f"deputy role did not drop after revoke: {me_revoked.json()}")
    after_admin = await delegated_client.get("/admin/departments")
    assert_true(after_admin.status_code == 403, f"deputy still accesses admin endpoint after revoke: {after_admin.status_code}")
    await delegated_client.aclose()
    return {"delegation_id": delegation["delegation_id"], "active_role": me_active.json().get("role"), "revoked_role": me_revoked.json().get("role")}


async def test_audit_pdf(admin_client):
    brand_res = await admin_client.get("/admin/branding")
    assert_true(brand_res.status_code == 200, f"branding fetch failed: {brand_res.status_code} {brand_res.text}")
    brand_name = brand_res.json().get("institution_name") or "AssetFlow Campus"
    dept = f"{RUN_ID} Audit Dept"
    base_item = {"asset_id": f"{RUN_ID}_AST", "tag": f"{RUN_ID}-TAG", "name": f"{RUN_ID} Audit Camera", "expected_location": "Evidence Room", "verification": "Verified", "note": "ok"}
    no_photo_id = f"audit_{RUN_ID.lower()}_nophoto"
    photo_id = f"audit_{RUN_ID.lower()}_photo"
    now_iso = datetime.now(timezone.utc).isoformat()
    db.audits.insert_many([
        {"audit_id": no_photo_id, "department": dept, "period": "July 2026", "auditors": ["QA"], "status": "Closed", "created_at": now_iso, "closed_at": now_iso, "items": [dict(base_item)]},
        {"audit_id": photo_id, "department": dept, "period": "July 2026", "auditors": ["QA"], "status": "Closed", "created_at": now_iso, "closed_at": now_iso, "items": [{**base_item, "photos": [{"public_id": f"{RUN_ID}/photo", "url": make_data_uri_png(), "uploaded_by": "QA", "uploaded_at": now_iso}]}]},
    ])
    no_res = await admin_client.get(f"/audits/{no_photo_id}/pdf")
    photo_res = await admin_client.get(f"/audits/{photo_id}/pdf")
    assert_true(no_res.status_code == 200, f"no-photo PDF failed: {no_res.status_code} {no_res.text[:200]}")
    assert_true(photo_res.status_code == 200, f"photo PDF failed: {photo_res.status_code} {photo_res.text[:200]}")
    assert_true(no_res.content.startswith(b"%PDF") and photo_res.content.startswith(b"%PDF"), "PDF responses do not start with %PDF")
    assert_true("application/pdf" in no_res.headers.get("content-type", ""), f"wrong PDF content-type {no_res.headers.get('content-type')}")
    text = extract_pdf_text(photo_res.content)
    assert_true(dept in text, f"PDF text missing department {dept}; text={text[:500]}")
    assert_true("Cycle ID:" in text, f"PDF text missing Cycle ID; text={text[:500]}")
    assert_true(brand_name in text, f"PDF text missing branding institution {brand_name}; text={text[:500]}")
    assert_true("Evidence photos" in text, f"PDF text missing Evidence photos heading; text={text[:500]}")
    size_delta = len(photo_res.content) - len(no_res.content)
    assert_true(size_delta > 1000, f"photo PDF not materially larger than no-photo PDF; delta={size_delta}, sizes={len(photo_res.content)}/{len(no_res.content)}")
    return {"brand_name": brand_name, "no_photo_pdf_bytes": len(no_res.content), "photo_pdf_bytes": len(photo_res.content), "size_delta": size_delta}


def cleanup(run_id):
    db.push_subs.delete_many({"endpoint": {"$regex": run_id}})
    db.maintenance.delete_many({"description": {"$regex": run_id}})
    db.activity.delete_many({"$or": [{"entity_id": {"$regex": run_id}}, {"metadata.public_id": {"$regex": run_id}}, {"after.name": {"$regex": run_id}}]})
    db.assets.delete_many({"$or": [{"name": {"$regex": run_id}}, {"tag": {"$regex": run_id}}, {"serial": {"$regex": run_id}}]})
    db.users.delete_many({"$or": [{"email": {"$regex": run_id.lower()}}, {"name": {"$regex": run_id}}]})
    db.delegations.update_many({"note": {"$regex": run_id}}, {"$set": {"status": "Revoked", "revoked_at": datetime.now(timezone.utc).isoformat()}})
    db.audits.delete_many({"audit_id": {"$regex": run_id.lower()}})


async def main():
    cleanup(RUN_ID)
    report = {"run_id": RUN_ID, "passed": [], "failed": [], "details": {}}
    admin_client = demo_client = None
    try:
        admin_client, admin_user = await login(ADMIN_EMAIL, ADMIN_PASSWORD)
        demo_client, demo_user = await login(DEMO_EMAIL, DEMO_PASSWORD)
        tests = [
            ("push_subscription_and_sw", test_push_subscription_and_sw(admin_client, admin_user)),
            ("push_send_code_path", test_push_send_code_path(admin_client)),
            ("bulk_import", test_bulk_import(admin_client, demo_client)),
            ("delegation", test_delegation(admin_client, demo_client, admin_user, demo_user)),
            ("audit_pdf", test_audit_pdf(admin_client)),
        ]
        for name, coro in tests:
            try:
                report["details"][name] = await coro
                report["passed"].append(name)
                print(f"PASS {name}")
            except Exception as exc:
                report["failed"].append({"test": name, "error": repr(exc)})
                print(f"FAIL {name}: {exc!r}")
                # Continue to collect as much focused evidence as possible.
    finally:
        if admin_client:
            await admin_client.aclose()
        if demo_client and not demo_client.is_closed:
            await demo_client.aclose()
        cleanup(RUN_ID)
        out_path = ROOT / "test_reports" / "bug_verification_iteration6_backend_results.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, indent=2, default=str))
        print(json.dumps(report, indent=2, default=str))
        mongo.close()
    if report["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())