#!/usr/bin/env python3
"""Focused backend verification for AssetFlow iteration 5 feature bugfixes."""
import datetime as dt
import io
import json
import os
import re
import sys
import time
from pathlib import Path

import requests
from pymongo import MongoClient

try:
    from PyPDF2 import PdfReader
except Exception as exc:  # pragma: no cover - test env guard
    PdfReader = None
    PDF_IMPORT_ERROR = str(exc)
else:
    PDF_IMPORT_ERROR = ""


ROOT = Path("/app")
API = "https://complete-coverage-3.preview.emergentagent.com/api"
ADMIN = {"email": "admin@assetflow.edu", "password": "Admin123!"}
DEMO = {"email": "demo@assetflow.edu", "password": "Campus123!"}
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
        if not line or line.strip().startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


class Runner:
    def __init__(self):
        self.results = []
        self.created_audit_id = None
        self.created_booking_id = None
        self.created_pending_email = None
        env = parse_env(ROOT / "backend" / ".env")
        self.mongo = MongoClient(env["MONGO_URL"], serverSelectionTimeoutMS=10000)
        self.db = self.mongo[env["DB_NAME"]]

    def check(self, name, ok, detail=""):
        self.results.append({"name": name, "ok": bool(ok), "detail": detail})
        print(("PASS" if ok else "FAIL") + f" - {name}" + (f": {detail}" if detail else ""))

    def login(self, creds):
        s = requests.Session()
        r = s.post(f"{API}/auth/login", json=creds, timeout=20)
        self.check(f"login {creds['email']}", r.status_code == 200, f"status={r.status_code}")
        return s

    def cleanup(self):
        try:
            if self.created_audit_id:
                self.db.audits.delete_one({"audit_id": self.created_audit_id})
            if self.created_booking_id:
                self.db.bookings.delete_one({"booking_id": self.created_booking_id})
            if self.created_pending_email:
                self.db.users.delete_many({"email": self.created_pending_email})
                self.db.user_sessions.delete_many({"email": self.created_pending_email})
            # Keep the seed maintenance card clean for the browser photo test.
            self.db.maintenance.update_one({"request_id": "mnt_seed_01"}, {"$set": {"photos": []}})
            # Required by handoff: restore branding defaults at the end of this backend run.
            self.db.branding.update_one({"_id": "singleton"}, {"$set": {**DEFAULT_BRAND, "updated_at": dt.datetime.now(dt.timezone.utc).isoformat(), "updated_by": "Bug Verification"}}, upsert=True)
        finally:
            self.mongo.close()

    def run(self):
        admin = self.login(ADMIN)
        demo = self.login(DEMO)

        # Cloudinary signature auth and folder restrictions.
        r = admin.get(f"{API}/uploads/signature", params={"folder": "assetflow/maintenance/TEST_backend"}, timeout=20)
        data = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        self.check("admin maintenance upload signature returns signed payload", r.status_code == 200 and all(data.get(k) for k in ["signature", "timestamp", "api_key", "cloud_name"]), f"status={r.status_code}, keys={sorted(data.keys())}")

        r = admin.get(f"{API}/uploads/signature", params={"folder": "assetflow/bad/TEST"}, timeout=20)
        self.check("invalid upload folder returns 400", r.status_code == 400, f"status={r.status_code}")

        r = demo.get(f"{API}/uploads/signature", params={"folder": "assetflow/branding/logo"}, timeout=20)
        self.check("branding upload folder is admin-only", r.status_code == 403, f"status={r.status_code}")

        r = demo.get(f"{API}/uploads/signature", params={"folder": "assetflow/maintenance/TEST_backend"}, timeout=20)
        self.check("non-admin can sign maintenance folder", r.status_code == 200, f"status={r.status_code}")

        # Branding default, validation, RBAC, save.
        self.db.branding.delete_one({"_id": "singleton"})
        r = demo.get(f"{API}/admin/branding", timeout=20)
        brand_default = r.json() if r.ok else {}
        self.check("branding GET returns defaults when no record exists", r.status_code == 200 and brand_default.get("institution_name") == "AssetFlow Campus" and brand_default.get("accent_color") == "#171717", f"status={r.status_code}, brand={brand_default}")

        r = demo.put(f"{API}/admin/branding", json={**DEFAULT_BRAND, "institution_name": "Should Not Save"}, timeout=20)
        self.check("non-admin branding PUT returns 403", r.status_code == 403, f"status={r.status_code}")

        r = admin.put(f"{API}/admin/branding", json={**DEFAULT_BRAND, "accent_color": "red"}, timeout=20)
        self.check("bad branding accent color returns 422", r.status_code == 422, f"status={r.status_code}")

        test_brand = {**DEFAULT_BRAND, "institution_name": "Test Institute", "tagline": "Accreditation Ready", "accreditation_body": "NAAC", "footer": "QA footer", "accent_color": "#7928ca", "logo_url": ""}
        r = admin.put(f"{API}/admin/branding", json=test_brand, timeout=20)
        self.check("admin branding PUT saves custom NAAC fields", r.status_code == 200 and r.json().get("institution_name") == "Test Institute" and r.json().get("accent_color") == "#7928ca", f"status={r.status_code}")

        # Weekly digest RBAC and shape.
        r = demo.get(f"{API}/digest/weekly", timeout=20)
        self.check("weekly digest rejects non-admin", r.status_code == 403, f"status={r.status_code}")

        r = admin.get(f"{API}/digest/weekly", timeout=20)
        digest = r.json() if r.ok else {}
        digest_ok = r.status_code == 200 and all(k in digest for k in ["kpis", "open_maintenance", "pending_users", "upcoming_bookings", "open_audits"]) and all(k in digest.get("kpis", {}) for k in ["open_maintenance", "pending_approvals", "utilization"])
        self.check("weekly digest returns KPI and list payload for admin", digest_ok, f"status={r.status_code}, keys={sorted(digest.keys()) if isinstance(digest, dict) else []}")

        # Audit evidence photo attach. Create an isolated audit cycle if necessary.
        r = admin.post(f"{API}/audits", json={"department": "Computer Science", "period": f"BugVerify {int(time.time())}", "auditors": ["QA"]}, timeout=20)
        audit = r.json() if r.ok else {}
        self.created_audit_id = audit.get("audit_id")
        first_item = (audit.get("items") or [{}])[0]
        photo_payload = {"public_id": f"assetflow/audits/TEST_backend_{int(time.time())}", "secure_url": "https://res.cloudinary.com/ifvlp2sb/image/upload/v1/assetflow/audits/TEST_backend.png", "width": 2, "height": 2}
        if self.created_audit_id and first_item.get("asset_id"):
            r = admin.post(f"{API}/audits/{self.created_audit_id}/items/{first_item['asset_id']}/photos", json=photo_payload, timeout=20)
            self.check("audit evidence Cloudinary URL attaches to audit item", r.status_code == 200 and r.json().get("photo", {}).get("url") == photo_payload["secure_url"], f"status={r.status_code}")
            r2 = admin.get(f"{API}/audits", timeout=20)
            audits = r2.json() if r2.ok else []
            persisted = any(a.get("audit_id") == self.created_audit_id and any(i.get("asset_id") == first_item["asset_id"] and any(p.get("public_id") == photo_payload["public_id"] for p in i.get("photos", [])) for i in a.get("items", [])) for a in audits)
            self.check("audit photo persists in GET /audits", persisted, f"audit_id={self.created_audit_id}")
        else:
            self.check("create audit with at least one item for evidence test", False, f"status={r.status_code}, audit={audit}")

        # NAAC PDF cover text and accent color stream.
        r = admin.get(f"{API}/reports/accreditation/download", params={"format": "pdf"}, timeout=30)
        pdf_ok = r.status_code == 200 and r.headers.get("content-type", "").startswith("application/pdf") and len(r.content) > 1000
        text = ""
        color_seen = False
        if pdf_ok and PdfReader:
            reader = PdfReader(io.BytesIO(r.content))
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
            streams = []
            for page in reader.pages:
                content = page.get_contents()
                if isinstance(content, list):
                    streams.extend((c.get_data().decode("latin1", "ignore") for c in content))
                elif content:
                    streams.append(content.get_data().decode("latin1", "ignore"))
            all_streams = "\n".join(streams)
            # ReportLab writes #7928ca approximately as .47451 .156863 .792157 rg.
            for match in re.finditer(r"([0-9.]+)\s+([0-9.]+)\s+([0-9.]+)\s+rg", all_streams):
                vals = [float(v) for v in match.groups()]
                if all(abs(a - b) < 0.003 for a, b in zip(vals, [121 / 255, 40 / 255, 202 / 255])):
                    color_seen = True
                    break
        self.check("PDF download returns a parseable PDF", pdf_ok and PdfReader is not None, f"status={r.status_code}, bytes={len(r.content)}, pdf_import_error={PDF_IMPORT_ERROR}")
        self.check("PDF cover includes saved institution name", "Test Institute" in text, f"text_excerpt={text[:120]!r}")
        self.check("PDF content stream includes saved accent color", color_seen, "expected #7928ca RGB tokens in reportlab stream")

        return self.results


if __name__ == "__main__":
    runner = Runner()
    try:
        results = runner.run()
    finally:
        runner.cleanup()
    out = {"ok": all(r["ok"] for r in results), "results": results}
    path = ROOT / "test_reports" / "bug_verification_5_backend_results.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=2))
    sys.exit(0 if out["ok"] else 1)