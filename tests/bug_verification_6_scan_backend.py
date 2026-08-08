#!/usr/bin/env python3
"""Focused iteration 6 verification for /scan served HTML and related regression APIs."""
import datetime as dt
import json
import re
import sys
import time
from pathlib import Path

import requests
from pymongo import MongoClient

ROOT = Path("/app")
BASE = "https://complete-coverage-3.preview.emergentagent.com"
API = f"{BASE}/api"
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

    def check(self, name, ok, detail=""):
        self.results.append({"name": name, "ok": bool(ok), "detail": detail})
        print(("PASS" if ok else "FAIL") + f" - {name}" + (f": {detail}" if detail else ""))

    def login(self, creds):
        s = requests.Session()
        r = s.post(f"{API}/auth/login", json=creds, timeout=25)
        self.check(f"login {creds['email']}", r.status_code == 200, f"status={r.status_code}; cookies={list(s.cookies.keys())}")
        return s

    @staticmethod
    def meta_content(html, name):
        m = re.search(r'<meta[^>]+name=["\']' + re.escape(name) + r'["\'][^>]*>', html, flags=re.I)
        if not m:
            return None
        c = re.search(r'content=["\']([^"\']+)["\']', m.group(0), flags=re.I)
        return c.group(1) if c else ""

    def run(self):
        admin = self.login(ADMIN)
        demo = self.login(DEMO)

        # Served SPA shell for the exact /scan route, using an authenticated browser-like session.
        r = admin.get(f"{BASE}/scan", timeout=25, headers={"Accept": "text/html"})
        html = r.text
        self.check("GET /scan returns HTML for authenticated session", r.status_code == 200 and "<html" in html.lower(), f"status={r.status_code}; content_type={r.headers.get('content-type')}")
        expected_metas = {
            "apple-mobile-web-app-capable": "yes",
            "mobile-web-app-capable": "yes",
            "apple-mobile-web-app-status-bar-style": "black-translucent",
        }
        for name, expected in expected_metas.items():
            actual = self.meta_content(html, name)
            self.check(f"/scan HTML head includes {name}", actual == expected, f"actual={actual!r}")
        title_ok = re.search(r"<title>\s*AssetFlow Campus\s*</title>", html, re.I) is not None
        self.check("/scan HTML head title is AssetFlow Campus", title_ok)

        # Contract asset used by the QR manual lookup.
        r = admin.get(f"{API}/assets/by-tag/AF-2025-1001", timeout=25)
        asset = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        self.check("AF-2025-1001 resolves through backend lookup", r.status_code == 200 and asset.get("tag") == "AF-2025-1001" and asset.get("asset_id"), f"status={r.status_code}; asset={asset}")
        self.check("AF-2025-1001 is available for Check-out CTA", asset.get("status") == "Available", f"status={asset.get('status')}")

        # Regression API smokes for the same iteration features.
        r = admin.get(f"{API}/digest/weekly", timeout=25)
        digest = r.json() if r.ok else {}
        self.check("weekly digest payload is available to admin", r.status_code == 200 and all(k in digest for k in ["kpis", "open_maintenance", "pending_users", "upcoming_bookings", "open_audits"]), f"status={r.status_code}")
        r = demo.get(f"{API}/digest/weekly", timeout=25)
        self.check("weekly digest still enforces admin RBAC", r.status_code == 403, f"status={r.status_code}")

        r = admin.get(f"{API}/uploads/signature", params={"folder": f"assetflow/maintenance/bug_verify_6_{int(time.time())}"}, timeout=25)
        sig = r.json() if r.ok else {}
        self.check("maintenance real-upload signature returns Cloudinary fields", r.status_code == 200 and all(sig.get(k) for k in ["signature", "timestamp", "api_key", "cloud_name"]), f"status={r.status_code}; keys={sorted(sig.keys()) if isinstance(sig, dict) else []}")

        # Audit evidence attach/persistence with a Cloudinary-shaped URL payload.
        r = admin.post(f"{API}/audits", json={"department": "Computer Science", "period": f"BugVerify6 {int(time.time())}", "auditors": ["QA"]}, timeout=25)
        audit = r.json() if r.ok else {}
        self.created_audit_id = audit.get("audit_id")
        item = (audit.get("items") or [{}])[0]
        if self.created_audit_id and item.get("asset_id"):
            photo = {"public_id": f"assetflow/audits/bug_verify_6_{int(time.time())}", "secure_url": "https://res.cloudinary.com/ifvlp2sb/image/upload/v1/assetflow/audits/bug_verify_6.png", "width": 2, "height": 2}
            r = admin.post(f"{API}/audits/{self.created_audit_id}/items/{item['asset_id']}/photos", json=photo, timeout=25)
            self.check("audit photo evidence endpoint accepts Cloudinary payload", r.status_code == 200 and r.json().get("photo", {}).get("url") == photo["secure_url"], f"status={r.status_code}")
            r = admin.get(f"{API}/audits", timeout=25)
            audits = r.json() if r.ok else []
            persisted = any(a.get("audit_id") == self.created_audit_id and any(i.get("asset_id") == item["asset_id"] and any(p.get("public_id") == photo["public_id"] for p in i.get("photos", [])) for i in a.get("items", [])) for a in audits)
            self.check("audit photo evidence persists in GET /audits", persisted, f"audit_id={self.created_audit_id}")
        else:
            self.check("created audit cycle with evidence item", False, f"status={r.status_code}; audit={audit}")

        # Branding/PDF cover regression smoke; restore defaults afterward.
        brand = {**DEFAULT_BRAND, "institution_name": "BugVerify6 Institute", "tagline": "Mobile corridor ready", "accreditation_body": "NAAC QA", "footer": "BugVerify6 footer", "accent_color": "#123abc"}
        r = admin.put(f"{API}/admin/branding", json=brand, timeout=25)
        self.check("admin branding save still works", r.status_code == 200 and r.json().get("institution_name") == brand["institution_name"], f"status={r.status_code}")
        r = admin.get(f"{API}/reports/accreditation/download", params={"format": "pdf"}, timeout=35)
        self.check("NAAC PDF cover export returns non-empty PDF", r.status_code == 200 and r.headers.get("content-type", "").startswith("application/pdf") and len(r.content) > 1000, f"status={r.status_code}; bytes={len(r.content)}")

        return self.results

    def cleanup(self):
        # Use API for safe cleanup where possible. Audit cleanup is left to DB cleanup in existing seed jobs if API lacks delete.
        try:
            s = self.login(ADMIN)
            s.put(f"{API}/admin/branding", json={**DEFAULT_BRAND, "updated_at": dt.datetime.now(dt.timezone.utc).isoformat()}, timeout=25)
        except Exception as exc:
            print(f"WARN - cleanup branding failed: {exc}")
        try:
            if self.created_audit_id:
                env = parse_env(ROOT / "backend" / ".env")
                mongo = MongoClient(env["MONGO_URL"], serverSelectionTimeoutMS=10000)
                mongo[env["DB_NAME"]].audits.delete_one({"audit_id": self.created_audit_id})
                mongo.close()
        except Exception as exc:
            print(f"WARN - cleanup audit failed: {exc}")


if __name__ == "__main__":
    runner = Runner()
    try:
        results = runner.run()
    finally:
        runner.cleanup()
    out = {"ok": all(r["ok"] for r in results), "results": results}
    path = ROOT / "test_reports" / "bug_verification_6_backend_results.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=2))
    sys.exit(0 if out["ok"] else 1)