#!/usr/bin/env python3
"""Focused bug-verification backend/API checks for AssetFlow maintenance/RBAC/Mongo flows."""

import json
import os
import time
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests
from pymongo import MongoClient


ROOT = Path("/app")
BACKEND_API = os.environ.get("BACKEND_API", "https://fluid-layout-pro.preview.emergentagent.com/api")


def read_env(path: Path):
    data = {}
    for raw in path.read_text().splitlines():
        raw = raw.strip()
        if not raw or raw.startswith("#") or "=" not in raw:
            continue
        k, v = raw.split("=", 1)
        data[k] = v.strip().strip('"').strip("'")
    return data


class CheckFailure(AssertionError):
    pass


class Runner:
    def __init__(self):
        self.results = []
        self.created_request_ids = set()
        self.created_user_emails = set()
        self.created_user_ids = set()
        self.env = read_env(ROOT / "backend" / ".env")
        self.mongo = MongoClient(self.env["MONGO_URL"], serverSelectionTimeoutMS=20000)
        self.db = self.mongo[self.env["DB_NAME"]]

    def record(self, name, ok, detail=""):
        print(f"{'PASS' if ok else 'FAIL'}: {name} {detail}")
        self.results.append({"name": name, "ok": ok, "detail": detail})

    def check(self, name, fn):
        try:
            detail = fn() or ""
            self.record(name, True, detail)
        except Exception as exc:  # noqa: BLE001 - test runner must continue
            self.record(name, False, repr(exc))

    def assert_true(self, cond, msg):
        if not cond:
            raise CheckFailure(msg)

    def session_login(self, email, password):
        s = requests.Session()
        r = s.post(f"{BACKEND_API}/auth/login", json={"email": email, "password": password}, timeout=30)
        self.assert_true(r.status_code == 200, f"login failed {email}: {r.status_code} {r.text[:200]}")
        self.assert_true("session_token" in s.cookies, f"session cookie missing for {email}")
        return s, r.json()

    def signup(self, name, email, password):
        s = requests.Session()
        r = s.post(f"{BACKEND_API}/auth/signup", json={"name": name, "email": email, "password": password}, timeout=30)
        self.assert_true(r.status_code in (200, 409), f"signup failed {email}: {r.status_code} {r.text[:200]}")
        if r.status_code == 409:
            s, user = self.session_login(email, password)
        else:
            user = r.json()
        self.created_user_emails.add(email)
        self.created_user_ids.add(user["user_id"])
        return s, user

    def api(self, sess, method, path, **kwargs):
        r = sess.request(method, f"{BACKEND_API}{path}", timeout=30, **kwargs)
        return r

    def create_maintenance(self, sess, desc, priority="Medium"):
        r = self.api(sess, "POST", "/maintenance", json={"asset_id": "ast_seed_2", "description": desc, "priority": priority})
        self.assert_true(r.status_code == 200, f"create maintenance failed: {r.status_code} {r.text[:200]}")
        data = r.json()
        self.created_request_ids.add(data["request_id"])
        return data

    def cleanup(self):
        if self.created_request_ids:
            self.db.maintenance.delete_many({"request_id": {"$in": list(self.created_request_ids)}})
            self.db.activity.delete_many({"entity_id": {"$in": list(self.created_request_ids)}})
        if self.created_user_emails:
            self.db.users.delete_many({"email": {"$in": list(self.created_user_emails)}})
        if self.created_user_ids:
            self.db.user_sessions.delete_many({"user_id": {"$in": list(self.created_user_ids)}})
            self.db.notification_state.delete_many({"user_id": {"$in": list(self.created_user_ids)}})
        self.db.maintenance.delete_many({"description": {"$regex": "^TEST_BUG4_"}})
        self.db.activity.delete_many({"metadata.test_run": "bug_verification_4"})

    def run(self):
        admin_s, admin = self.session_login("admin@assetflow.edu", "Admin123!")
        manager_s, _manager = self.session_login("demo@assetflow.edu", "Campus123!")

        def env_and_mongo():
            self.assert_true("mongodb+srv://bisenm2006_db_user:ayush@100xmikey.olgetcs.mongodb.net/" in self.env["MONGO_URL"], self.env["MONGO_URL"])
            self.assert_true(self.env["DB_NAME"] == "assetflow_campus", self.env["DB_NAME"])
            self.mongo.admin.command("ping")
            return f"DB={self.env['DB_NAME']} ping ok"

        self.check("backend .env points to requested Atlas DB and Mongo ping succeeds", env_and_mongo)

        def counts_stable():
            r1 = self.api(admin_s, "GET", "/dashboard")
            self.assert_true(r1.status_code == 200, r1.text[:200])
            c1 = r1.json()["kpis"]
            time.sleep(1.2)
            r2 = self.api(admin_s, "GET", "/dashboard")
            self.assert_true(r2.status_code == 200, r2.text[:200])
            c2 = r2.json()["kpis"]
            keys = ["total_assets", "available"]
            self.assert_true({k: c1[k] for k in keys} == {k: c2[k] for k in keys}, f"counts changed {c1} -> {c2}")
            return json.dumps({"first": c1, "second": c2})

        self.check("authenticated endpoints work and count fetch is stable across delay", counts_stable)

        def maintenance_status_flow():
            req = self.create_maintenance(manager_s, f"TEST_BUG4_STATUS_FLOW_{uuid.uuid4().hex}", "High")
            statuses = ["Approved", "In progress", "Resolved"]
            last = req
            for status in statuses:
                r = self.api(manager_s, "PATCH", f"/maintenance/{req['request_id']}", json={"status": status})
                self.assert_true(r.status_code == 200, f"PATCH {status}: {r.status_code} {r.text[:200]}")
                last = r.json()
                self.assert_true(last["status"] == status, f"expected {status}, got {last}")
            self.assert_true("resolved_at" in last, "resolved_at missing after resolved")
            r = self.api(manager_s, "DELETE", f"/maintenance/{req['request_id']}")
            self.assert_true(r.status_code == 200 and r.json().get("ok") is True, f"delete failed {r.status_code} {r.text[:200]}")
            self.created_request_ids.discard(req["request_id"])
            return req["request_id"]

        self.check("maintenance POST/PATCH Approved/In progress/Resolved/DELETE works", maintenance_status_flow)

        def maintenance_reject_flow():
            req = self.create_maintenance(manager_s, f"TEST_BUG4_REJECT_FLOW_{uuid.uuid4().hex}", "Medium")
            r = self.api(manager_s, "PATCH", f"/maintenance/{req['request_id']}", json={"status": "Rejected"})
            self.assert_true(r.status_code == 200, f"reject failed {r.status_code} {r.text[:200]}")
            data = r.json()
            self.assert_true(data["status"] == "Rejected" and "rejected_at" in data, f"bad reject payload {data}")
            r2 = self.api(manager_s, "PATCH", f"/maintenance/{req['request_id']}", json={"status": "Pending"})
            self.assert_true(r2.status_code == 200 and r2.json()["status"] == "Pending", f"reopen failed {r2.status_code} {r2.text[:200]}")
            r3 = self.api(manager_s, "DELETE", f"/maintenance/{req['request_id']}")
            self.assert_true(r3.status_code == 200, f"delete rejected request failed {r3.status_code} {r3.text[:200]}")
            self.created_request_ids.discard(req["request_id"])
            return req["request_id"]

        self.check("maintenance Rejected status and manual reopen/delete backend flow works", maintenance_reject_flow)

        def auto_delete_30d():
            rid = f"mnt_TEST_BUG4_OLD_{uuid.uuid4().hex[:10]}"
            self.created_request_ids.add(rid)
            old = (datetime.now(timezone.utc) - timedelta(days=40)).isoformat()
            doc = {"request_id": rid, "asset_id": "ast_seed_2", "description": f"TEST_BUG4_OLD_RESOLVED_{uuid.uuid4().hex}", "priority": "Low", "raised_by": admin["name"], "raised_by_id": admin["user_id"], "status": "Resolved", "created_at": old, "resolved_at": old}
            self.db.maintenance.insert_one(doc)
            self.assert_true(self.db.maintenance.count_documents({"request_id": rid}) == 1, "seed old resolved not inserted")
            r = self.api(admin_s, "GET", "/maintenance")
            self.assert_true(r.status_code == 200, f"GET maintenance failed: {r.status_code} {r.text[:200]}")
            self.assert_true(self.db.maintenance.count_documents({"request_id": rid}) == 0, "old resolved request was not purged")
            self.created_request_ids.discard(rid)
            event = self.db.activity.find_one({"actor_id": "system", "entity_type": "maintenance", "action": {"$regex": "auto-expired .* resolved requests"}}, sort=[("timestamp", -1)])
            self.assert_true(event is not None, "auto-expire activity event missing")
            return event["action"]

        self.check("GET /maintenance auto-deletes resolved records older than 30 days and logs activity", auto_delete_30d)

        def rbac_student_delete_other():
            suffix = uuid.uuid4().hex[:8]
            a_s, a = self.signup("TEST BUG4 Student A", f"test_bug4_student_a_{suffix}@assetflow.edu", "Campus123!")
            b_s, _b = self.signup("TEST BUG4 Student B", f"test_bug4_student_b_{suffix}@assetflow.edu", "Campus123!")
            req = self.create_maintenance(a_s, f"TEST_BUG4_STUDENT_OWNED_{suffix}", "Low")
            r_patch = self.api(a_s, "PATCH", f"/maintenance/{req['request_id']}", json={"status": "Approved"})
            self.assert_true(r_patch.status_code == 200, f"student patch should be allowed: {r_patch.status_code} {r_patch.text[:200]}")
            r = self.api(b_s, "DELETE", f"/maintenance/{req['request_id']}")
            self.assert_true(r.status_code == 403, f"expected 403 deleting another user's request, got {r.status_code} {r.text[:200]}")
            r_owner = self.api(a_s, "DELETE", f"/maintenance/{req['request_id']}")
            self.assert_true(r_owner.status_code == 200, f"owner student delete should work: {r_owner.status_code} {r_owner.text[:200]}")
            self.created_request_ids.discard(req["request_id"])
            return r.text[:120]

        self.check("maintenance DELETE RBAC blocks Student deleting another user's request", rbac_student_delete_other)

        def regressions_api():
            suffix = uuid.uuid4().hex[:8]
            student_s, _student = self.signup("TEST BUG4 RBAC Student", f"test_bug4_rbac_{suffix}@assetflow.edu", "Campus123!")
            forbidden_admin = self.api(student_s, "GET", "/admin/users")
            self.assert_true(forbidden_admin.status_code == 403, f"student admin/users should be 403: {forbidden_admin.status_code} {forbidden_admin.text[:200]}")
            forbidden_reports = self.api(student_s, "GET", "/reports")
            self.assert_true(forbidden_reports.status_code == 403, f"student reports should be 403: {forbidden_reports.status_code} {forbidden_reports.text[:200]}")
            notif = self.api(admin_s, "GET", "/notifications")
            self.assert_true(notif.status_code == 200 and "items" in notif.json() and "unread" in notif.json(), notif.text[:200])
            mark = self.api(admin_s, "POST", "/notifications/mark-all-read")
            self.assert_true(mark.status_code == 200 and mark.json().get("ok"), mark.text[:200])
            role = self.api(admin_s, "GET", "/admin/role-preview/Student")
            self.assert_true(role.status_code == 200 and "/maintenance" in role.json().get("visible_pages", []), role.text[:200])
            csv = self.api(admin_s, "GET", "/reports/accreditation/download?format=csv")
            self.assert_true(csv.status_code == 200 and "text/csv" in csv.headers.get("content-type", ""), f"csv {csv.status_code} {csv.headers}")
            pdf = self.api(admin_s, "GET", "/reports/accreditation/download?format=pdf")
            self.assert_true(pdf.status_code == 200 and "application/pdf" in pdf.headers.get("content-type", ""), f"pdf {pdf.status_code} {pdf.headers}")
            dept = self.api(admin_s, "POST", "/admin/departments", json={"name": "   "})
            cat = self.api(admin_s, "POST", "/admin/categories", json={"name": "   "})
            self.assert_true(dept.status_code == 422, f"blank dept should be 422: {dept.status_code} {dept.text[:200]}")
            self.assert_true(cat.status_code == 422, f"blank category should be 422: {cat.status_code} {cat.text[:200]}")
            assets = self.api(admin_s, "GET", "/assets")
            self.assert_true(assets.status_code == 200 and len(assets.json()) > 0, assets.text[:200])
            tag = assets.json()[0]["tag"]
            qr = self.api(admin_s, "GET", f"/assets/by-tag/{tag}")
            self.assert_true(qr.status_code == 200 and qr.json()["tag"] == tag, qr.text[:200])
            return "strict RBAC denials, notifications, role preview, CSV/PDF, blank validators, QR by-tag ok"

        self.check("regression API checks for RBAC/notifications/role-preview/downloads/validators/QR", regressions_api)

        self.cleanup()
        failed = [r for r in self.results if not r["ok"]]
        out = {"backend_api": BACKEND_API, "total": len(self.results), "passed": len(self.results) - len(failed), "failed": failed, "results": self.results}
        print("RESULT_JSON=" + json.dumps(out, default=str))
        return 1 if failed else 0


if __name__ == "__main__":
    runner = Runner()
    try:
        code = runner.run()
    finally:
        runner.cleanup()
    raise SystemExit(code)