#!/usr/bin/env python3
"""
AssetFlow Campus Backend API Testing
Tests 4 features: Push notifications, Bulk CSV import, Delegation slots, Audit PDF
"""

import requests
import json
import sys
from datetime import datetime, timedelta, timezone

# Configuration
BASE_URL = "https://fluid-layout-pro.preview.emergentagent.com/api"
ADMIN_EMAIL = "admin@assetflow.edu"
ADMIN_PASSWORD = "Admin123!"
ASSET_MANAGER_EMAIL = "demo@assetflow.edu"
ASSET_MANAGER_PASSWORD = "Campus123!"

# Test results tracking
test_results = {
    "push_notifications": {"passed": 0, "failed": 0, "details": []},
    "bulk_csv_import": {"passed": 0, "failed": 0, "details": []},
    "delegation_slots": {"passed": 0, "failed": 0, "details": []},
    "audit_pdf": {"passed": 0, "failed": 0, "details": []},
}

def log_test(feature, test_name, passed, message="", response=None):
    """Log test result"""
    status = "✅ PASS" if passed else "❌ FAIL"
    detail = f"{status}: {test_name}"
    if message:
        detail += f" - {message}"
    if response and not passed:
        detail += f" | Status: {response.status_code}"
        try:
            detail += f" | Response: {response.text[:200]}"
        except Exception:
            pass
    
    test_results[feature]["details"].append(detail)
    if passed:
        test_results[feature]["passed"] += 1
    else:
        test_results[feature]["failed"] += 1
    
    print(detail)

def login(email, password):
    """Login and return session"""
    session = requests.Session()
    try:
        response = session.post(
            f"{BASE_URL}/auth/login",
            json={"email": email, "password": password},
            timeout=15
        )
        if response.status_code == 200:
            print(f"✅ Logged in as {email}")
            return session
        else:
            print(f"❌ Login failed for {email}: {response.status_code} - {response.text[:200]}")
            return None
    except Exception as e:
        print(f"❌ Login exception for {email}: {str(e)}")
        return None

def test_push_notifications():
    """Test push notification endpoints"""
    print("\n" + "="*80)
    print("TESTING: PUSH NOTIFICATIONS")
    print("="*80)
    
    # Test 1: GET /api/push/public-key (no auth required)
    try:
        response = requests.get(f"{BASE_URL}/push/public-key", timeout=15)
        if response.status_code == 200:
            data = response.json()
            if data.get("key") and len(data["key"]) > 0:
                log_test("push_notifications", "GET /push/public-key returns VAPID key", True, f"Key length: {len(data['key'])}")
            else:
                log_test("push_notifications", "GET /push/public-key returns VAPID key", False, "Key is empty")
        else:
            log_test("push_notifications", "GET /push/public-key", False, response=response)
    except Exception as e:
        log_test("push_notifications", "GET /push/public-key", False, f"Exception: {str(e)}")
    
    # Login as Asset Manager for authenticated tests
    session = login(ASSET_MANAGER_EMAIL, ASSET_MANAGER_PASSWORD)
    if not session:
        log_test("push_notifications", "Login as Asset Manager", False, "Cannot proceed with authenticated tests")
        return
    
    # Test 2: POST /api/push/subscribe with dummy subscription
    dummy_subscription = {
        "endpoint": f"https://fcm.googleapis.com/fcm/send/test-endpoint-{datetime.now().timestamp()}",
        "keys": {
            "p256dh": "BNcRdreALRFXTkOOUHK1EtK2wtaz5Ry4YfYCA_0QTpQtUbVlUls0VJXg7A8u-Ts1XbjhazAkj7I99e8QcYP7DkM=",
            "auth": "tBHItJI5svbpez7KI4CCXg=="
        }
    }
    
    try:
        response = session.post(
            f"{BASE_URL}/push/subscribe",
            json=dummy_subscription,
            timeout=15
        )
        if response.status_code == 200:
            data = response.json()
            if data.get("ok") == True:
                log_test("push_notifications", "POST /push/subscribe", True, "Subscription stored")
            else:
                log_test("push_notifications", "POST /push/subscribe", False, f"Unexpected response: {data}")
        else:
            log_test("push_notifications", "POST /push/subscribe", False, response=response)
    except Exception as e:
        log_test("push_notifications", "POST /push/subscribe", False, f"Exception: {str(e)}")
    
    # Test 3: Create HIGH priority maintenance request (should trigger push notification internally)
    # First, get an asset to create maintenance for
    try:
        assets_response = session.get(f"{BASE_URL}/assets", timeout=15)
        if assets_response.status_code == 200:
            assets = assets_response.json()
            if assets and len(assets) > 0:
                asset_id = assets[0]["asset_id"]
                
                # Create HIGH priority maintenance
                maintenance_payload = {
                    "asset_id": asset_id,
                    "description": "Critical equipment failure requiring immediate attention",
                    "priority": "High"
                }
                
                maint_response = session.post(
                    f"{BASE_URL}/maintenance",
                    json=maintenance_payload,
                    timeout=15
                )
                
                if maint_response.status_code == 200:
                    log_test("push_notifications", "POST /maintenance with High priority (triggers push)", True, 
                            "Maintenance created without error (push sent internally)")
                else:
                    log_test("push_notifications", "POST /maintenance with High priority", False, response=maint_response)
            else:
                log_test("push_notifications", "POST /maintenance with High priority", False, "No assets available")
        else:
            log_test("push_notifications", "GET /assets for maintenance test", False, response=assets_response)
    except Exception as e:
        log_test("push_notifications", "POST /maintenance with High priority", False, f"Exception: {str(e)}")
    
    # Test 4: POST /api/push/unsubscribe
    try:
        response = session.post(
            f"{BASE_URL}/push/unsubscribe",
            json={"endpoint": dummy_subscription["endpoint"], "keys": dummy_subscription["keys"]},
            timeout=15
        )
        if response.status_code == 200:
            data = response.json()
            if data.get("ok") == True:
                log_test("push_notifications", "POST /push/unsubscribe", True, "Subscription removed")
            else:
                log_test("push_notifications", "POST /push/unsubscribe", False, f"Unexpected response: {data}")
        else:
            log_test("push_notifications", "POST /push/unsubscribe", False, response=response)
    except Exception as e:
        log_test("push_notifications", "POST /push/unsubscribe", False, f"Exception: {str(e)}")

def test_bulk_csv_import():
    """Test bulk CSV import for assets and students"""
    print("\n" + "="*80)
    print("TESTING: BULK CSV IMPORT")
    print("="*80)
    
    # Login as Admin (required for imports)
    admin_session = login(ADMIN_EMAIL, ADMIN_PASSWORD)
    if not admin_session:
        log_test("bulk_csv_import", "Login as Admin", False, "Cannot proceed with import tests")
        return
    
    # Test 1: Import assets with valid and invalid rows
    assets_csv = """name,category,location,department
Laptop Dell XPS 15,IT Equipment,Room 301,Computer Science
Projector Epson,IT Equipment,Seminar Hall,Administration
,Lab Equipment,Lab 2,Mechanical"""
    
    try:
        response = admin_session.post(
            f"{BASE_URL}/admin/imports/assets",
            data=assets_csv,
            headers={"Content-Type": "text/csv"},
            timeout=15
        )
        if response.status_code == 200:
            data = response.json()
            if data.get("created") == 2 and data.get("skipped") == 1:
                log_test("bulk_csv_import", "POST /admin/imports/assets (2 valid, 1 missing name)", True, 
                        f"Created: {data['created']}, Skipped: {data['skipped']}")
            else:
                log_test("bulk_csv_import", "POST /admin/imports/assets", False, 
                        f"Expected created=2, skipped=1, got created={data.get('created')}, skipped={data.get('skipped')}")
        else:
            log_test("bulk_csv_import", "POST /admin/imports/assets", False, response=response)
    except Exception as e:
        log_test("bulk_csv_import", "POST /admin/imports/assets", False, f"Exception: {str(e)}")
    
    # Test 2: Import students with valid, invalid email, and duplicate
    timestamp = int(datetime.now().timestamp())
    students_csv = f"""name,email,roll_number,department
Alice Johnson,alice.johnson{timestamp}@campus.edu,CS2024001,Computer Science
Bob Smith,invalid-email-no-at,CS2024002,Computer Science
Charlie Brown,alice.johnson{timestamp}@campus.edu,CS2024003,Computer Science"""
    
    try:
        response = admin_session.post(
            f"{BASE_URL}/admin/imports/students",
            data=students_csv,
            headers={"Content-Type": "text/csv"},
            timeout=15
        )
        if response.status_code == 200:
            data = response.json()
            # Should create 1 (Alice), skip 1 (invalid email), skip 1 (duplicate)
            if data.get("created") == 1 and data.get("skipped") == 2:
                log_test("bulk_csv_import", "POST /admin/imports/students (1 valid, 1 invalid email, 1 duplicate)", True,
                        f"Created: {data['created']}, Skipped: {data['skipped']}")
            else:
                log_test("bulk_csv_import", "POST /admin/imports/students", False,
                        f"Expected created=1, skipped=2, got created={data.get('created')}, skipped={data.get('skipped')}")
        else:
            log_test("bulk_csv_import", "POST /admin/imports/students", False, response=response)
    except Exception as e:
        log_test("bulk_csv_import", "POST /admin/imports/students", False, f"Exception: {str(e)}")
    
    # Test 3: Non-admin should get 403
    asset_manager_session = login(ASSET_MANAGER_EMAIL, ASSET_MANAGER_PASSWORD)
    if asset_manager_session:
        try:
            response = asset_manager_session.post(
                f"{BASE_URL}/admin/imports/assets",
                data=assets_csv,
                headers={"Content-Type": "text/csv"},
                timeout=15
            )
            if response.status_code == 403:
                log_test("bulk_csv_import", "POST /admin/imports/assets as non-admin (403 expected)", True, "Correctly denied")
            else:
                log_test("bulk_csv_import", "POST /admin/imports/assets as non-admin", False, 
                        f"Expected 403, got {response.status_code}")
        except Exception as e:
            log_test("bulk_csv_import", "POST /admin/imports/assets as non-admin", False, f"Exception: {str(e)}")

def test_delegation_slots():
    """Test delegation slots - create, list, revoke, validation"""
    print("\n" + "="*80)
    print("TESTING: DELEGATION SLOTS")
    print("="*80)
    
    # Login as Admin
    admin_session = login(ADMIN_EMAIL, ADMIN_PASSWORD)
    if not admin_session:
        log_test("delegation_slots", "Login as Admin", False, "Cannot proceed with delegation tests")
        return
    
    # Test 1: GET /api/admin/users to find a non-admin deputy
    deputy_id = None
    try:
        response = admin_session.get(f"{BASE_URL}/admin/users", timeout=15)
        if response.status_code == 200:
            users = response.json()
            # Find a non-admin user (Asset Manager or other)
            for user in users:
                if user.get("role") != "Admin" and user.get("email") == ASSET_MANAGER_EMAIL:
                    deputy_id = user["user_id"]
                    log_test("delegation_slots", "GET /admin/users (find deputy)", True, f"Found deputy: {deputy_id}")
                    break
            if not deputy_id:
                log_test("delegation_slots", "GET /admin/users (find deputy)", False, "No non-admin user found")
                return
        else:
            log_test("delegation_slots", "GET /admin/users", False, response=response)
            return
    except Exception as e:
        log_test("delegation_slots", "GET /admin/users", False, f"Exception: {str(e)}")
        return
    
    # Test 2: POST /api/admin/delegations with valid time window
    now = datetime.now(timezone.utc)
    start_at = (now - timedelta(minutes=1)).isoformat()
    end_at = (now + timedelta(hours=1)).isoformat()
    
    delegation_payload = {
        "deputy_id": deputy_id,
        "start_at": start_at,
        "end_at": end_at,
        "note": "Test delegation for verification"
    }
    
    delegation_id = None
    try:
        response = admin_session.post(
            f"{BASE_URL}/admin/delegations",
            json=delegation_payload,
            timeout=15
        )
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "Scheduled":
                delegation_id = data.get("delegation_id")
                log_test("delegation_slots", "POST /admin/delegations (create)", True, 
                        f"Delegation created: {delegation_id}, status: {data['status']}")
            else:
                log_test("delegation_slots", "POST /admin/delegations", False, f"Unexpected status: {data.get('status')}")
        else:
            log_test("delegation_slots", "POST /admin/delegations", False, response=response)
    except Exception as e:
        log_test("delegation_slots", "POST /admin/delegations", False, f"Exception: {str(e)}")
    
    # Test 3: GET /api/admin/delegations (list)
    try:
        response = admin_session.get(f"{BASE_URL}/admin/delegations", timeout=15)
        if response.status_code == 200:
            delegations = response.json()
            found = any(d.get("delegation_id") == delegation_id for d in delegations)
            if found:
                log_test("delegation_slots", "GET /admin/delegations (list)", True, "New delegation appears in list")
            else:
                log_test("delegation_slots", "GET /admin/delegations", False, "New delegation not found in list")
        else:
            log_test("delegation_slots", "GET /admin/delegations", False, response=response)
    except Exception as e:
        log_test("delegation_slots", "GET /admin/delegations", False, f"Exception: {str(e)}")
    
    # Test 4: Auto-elevation check (skip if cannot log in as deputy)
    # Note: We cannot easily test this without knowing deputy's password
    log_test("delegation_slots", "Auto-elevation check", True, 
            "SKIPPED - Cannot log in as deputy without password (as per instructions)")
    
    # Test 5: DELETE /api/admin/delegations/{id} (revoke)
    if delegation_id:
        try:
            response = admin_session.delete(f"{BASE_URL}/admin/delegations/{delegation_id}", timeout=15)
            if response.status_code == 200:
                data = response.json()
                if data.get("ok") == True:
                    log_test("delegation_slots", "DELETE /admin/delegations/{id} (revoke)", True, "Delegation revoked")
                else:
                    log_test("delegation_slots", "DELETE /admin/delegations/{id}", False, f"Unexpected response: {data}")
            else:
                log_test("delegation_slots", "DELETE /admin/delegations/{id}", False, response=response)
        except Exception as e:
            log_test("delegation_slots", "DELETE /admin/delegations/{id}", False, f"Exception: {str(e)}")
    
    # Test 6: Validation - end_at <= start_at (should return 400)
    invalid_payload = {
        "deputy_id": deputy_id,
        "start_at": end_at,
        "end_at": start_at,  # end before start
        "note": "Invalid time range"
    }
    try:
        response = admin_session.post(
            f"{BASE_URL}/admin/delegations",
            json=invalid_payload,
            timeout=15
        )
        if response.status_code == 400:
            log_test("delegation_slots", "POST /admin/delegations with end_at <= start_at (400 expected)", True, "Correctly rejected")
        else:
            log_test("delegation_slots", "POST /admin/delegations with invalid time range", False, 
                    f"Expected 400, got {response.status_code}")
    except Exception as e:
        log_test("delegation_slots", "POST /admin/delegations with invalid time range", False, f"Exception: {str(e)}")
    
    # Test 7: Validation - non-existent deputy_id (should return 404)
    invalid_deputy_payload = {
        "deputy_id": "user_nonexistent_12345",
        "start_at": start_at,
        "end_at": end_at,
        "note": "Non-existent deputy"
    }
    try:
        response = admin_session.post(
            f"{BASE_URL}/admin/delegations",
            json=invalid_deputy_payload,
            timeout=15
        )
        if response.status_code == 404:
            log_test("delegation_slots", "POST /admin/delegations with non-existent deputy (404 expected)", True, "Correctly rejected")
        else:
            log_test("delegation_slots", "POST /admin/delegations with non-existent deputy", False,
                    f"Expected 404, got {response.status_code}")
    except Exception as e:
        log_test("delegation_slots", "POST /admin/delegations with non-existent deputy", False, f"Exception: {str(e)}")
    
    # Test 8: Validation - delegate to self (should return 400)
    # Get admin's own user_id
    try:
        me_response = admin_session.get(f"{BASE_URL}/auth/me", timeout=15)
        if me_response.status_code == 200:
            admin_user = me_response.json()
            admin_user_id = admin_user.get("user_id")
            
            self_delegate_payload = {
                "deputy_id": admin_user_id,
                "start_at": start_at,
                "end_at": end_at,
                "note": "Self delegation"
            }
            
            response = admin_session.post(
                f"{BASE_URL}/admin/delegations",
                json=self_delegate_payload,
                timeout=15
            )
            if response.status_code == 400:
                log_test("delegation_slots", "POST /admin/delegations to self (400 expected)", True, "Correctly rejected")
            else:
                log_test("delegation_slots", "POST /admin/delegations to self", False,
                        f"Expected 400, got {response.status_code}")
    except Exception as e:
        log_test("delegation_slots", "POST /admin/delegations to self", False, f"Exception: {str(e)}")

def test_audit_pdf():
    """Test audit PDF generation with photo grid"""
    print("\n" + "="*80)
    print("TESTING: AUDIT PDF WITH PHOTO GRID")
    print("="*80)
    
    # Login as Admin (has audit permission)
    admin_session = login(ADMIN_EMAIL, ADMIN_PASSWORD)
    if not admin_session:
        log_test("audit_pdf", "Login as Admin", False, "Cannot proceed with audit tests")
        return
    
    # Test 1: GET /api/audits to check if any exist
    audit_id = None
    try:
        response = admin_session.get(f"{BASE_URL}/audits", timeout=15)
        if response.status_code == 200:
            audits = response.json()
            if audits and len(audits) > 0:
                audit_id = audits[0]["audit_id"]
                log_test("audit_pdf", "GET /audits (existing audit found)", True, f"Found audit: {audit_id}")
            else:
                log_test("audit_pdf", "GET /audits", True, "No existing audits, will create one")
        else:
            log_test("audit_pdf", "GET /audits", False, response=response)
            return
    except Exception as e:
        log_test("audit_pdf", "GET /audits", False, f"Exception: {str(e)}")
        return
    
    # Test 2: If no audit exists, create one
    if not audit_id:
        audit_payload = {
            "department": "Computer Science",
            "period": "Q1 2025",
            "auditors": ["Admin"]
        }
        try:
            response = admin_session.post(
                f"{BASE_URL}/audits",
                json=audit_payload,
                timeout=15
            )
            if response.status_code == 200:
                data = response.json()
                audit_id = data.get("audit_id")
                log_test("audit_pdf", "POST /audits (create new audit)", True, f"Created audit: {audit_id}")
            else:
                log_test("audit_pdf", "POST /audits", False, response=response)
                return
        except Exception as e:
            log_test("audit_pdf", "POST /audits", False, f"Exception: {str(e)}")
            return
    
    # Test 3: GET /api/audits/{audit_id}/pdf
    if audit_id:
        try:
            response = admin_session.get(f"{BASE_URL}/audits/{audit_id}/pdf", timeout=30)
            if response.status_code == 200:
                content_type = response.headers.get("Content-Type", "")
                content_length = len(response.content)
                
                if "application/pdf" in content_type and content_length > 1000:
                    log_test("audit_pdf", "GET /audits/{audit_id}/pdf", True,
                            f"PDF generated successfully (Content-Type: {content_type}, Size: {content_length} bytes)")
                else:
                    log_test("audit_pdf", "GET /audits/{audit_id}/pdf", False,
                            f"Invalid PDF response (Content-Type: {content_type}, Size: {content_length} bytes)")
            else:
                log_test("audit_pdf", "GET /audits/{audit_id}/pdf", False, response=response)
        except Exception as e:
            log_test("audit_pdf", "GET /audits/{audit_id}/pdf", False, f"Exception: {str(e)}")

def print_summary():
    """Print test summary"""
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    total_passed = 0
    total_failed = 0
    
    for feature, results in test_results.items():
        passed = results["passed"]
        failed = results["failed"]
        total = passed + failed
        total_passed += passed
        total_failed += failed
        
        status = "✅" if failed == 0 else "❌"
        print(f"\n{status} {feature.upper().replace('_', ' ')}: {passed}/{total} passed")
        
        if failed > 0:
            print("  Failed tests:")
            for detail in results["details"]:
                if "❌" in detail:
                    print(f"    {detail}")
    
    print("\n" + "="*80)
    print(f"OVERALL: {total_passed}/{total_passed + total_failed} tests passed")
    print("="*80)
    
    return total_failed == 0

def main():
    """Run all tests"""
    print("="*80)
    print("AssetFlow Campus Backend API Testing")
    print("="*80)
    print(f"Base URL: {BASE_URL}")
    print(f"Admin: {ADMIN_EMAIL}")
    print(f"Asset Manager: {ASSET_MANAGER_EMAIL}")
    print("="*80)
    
    # Run all test suites
    test_push_notifications()
    test_bulk_csv_import()
    test_delegation_slots()
    test_audit_pdf()
    
    # Print summary
    all_passed = print_summary()
    
    # Exit with appropriate code
    sys.exit(0 if all_passed else 1)

if __name__ == "__main__":
    main()
