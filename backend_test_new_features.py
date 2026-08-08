#!/usr/bin/env python3
"""
AssetFlow Campus Backend API Testing - New Features
Tests: Bulk role assign, Unified search, Extended create fields
"""

import requests
import json
import sys
from datetime import datetime, timedelta

# Configuration
BASE_URL = "https://fluid-layout-pro.preview.emergentagent.com/api"
ADMIN_EMAIL = "admin@assetflow.edu"
ADMIN_PASSWORD = "Admin123!"
ASSET_MANAGER_EMAIL = "demo@assetflow.edu"
ASSET_MANAGER_PASSWORD = "Campus123!"

# Test results tracking
test_results = {
    "bulk_role_assign": {"passed": 0, "failed": 0, "details": []},
    "unified_search": {"passed": 0, "failed": 0, "details": []},
    "extended_create_fields": {"passed": 0, "failed": 0, "details": []},
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
            detail += f" | Response: {response.text[:300]}"
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

def test_bulk_role_assign():
    """Test bulk role assignment endpoint"""
    print("\n" + "="*80)
    print("TESTING: BULK ROLE ASSIGN - POST /admin/users/bulk-role")
    print("="*80)
    
    # Login as Admin
    admin_session = login(ADMIN_EMAIL, ADMIN_PASSWORD)
    if not admin_session:
        log_test("bulk_role_assign", "Admin login", False, "Cannot proceed with tests")
        return
    
    # Test 1: Get all users to find non-admin user IDs
    try:
        response = admin_session.get(f"{BASE_URL}/admin/users", timeout=15)
        if response.status_code == 200:
            users = response.json()
            log_test("bulk_role_assign", "GET /admin/users", True, f"Found {len(users)} users")
            
            # Find ananya and vikram (students)
            ananya = next((u for u in users if u.get("email") == "ananya@assetflow.edu"), None)
            vikram = next((u for u in users if u.get("email") == "vikram@assetflow.edu"), None)
            admin_user = next((u for u in users if u.get("email") == ADMIN_EMAIL), None)
            
            if not ananya or not vikram:
                log_test("bulk_role_assign", "Find test users (ananya/vikram)", False, "Test users not found in database")
                return
            
            ananya_id = ananya.get("user_id")
            vikram_id = vikram.get("user_id")
            admin_id = admin_user.get("user_id") if admin_user else None
            
            log_test("bulk_role_assign", "Find test users", True, f"ananya: {ananya_id}, vikram: {vikram_id}")
            
            # Test 2: Bulk assign Asset Manager role to ananya and vikram
            bulk_payload = {
                "user_ids": [ananya_id, vikram_id],
                "role": "Asset Manager",
                "status": "Active"
            }
            response = admin_session.post(f"{BASE_URL}/admin/users/bulk-role", json=bulk_payload, timeout=15)
            if response.status_code == 200:
                data = response.json()
                if data.get("updated") == 2 and len(data.get("skipped", [])) == 0:
                    log_test("bulk_role_assign", "Bulk assign Asset Manager to 2 users", True, f"Updated: {data['updated']}, Skipped: {len(data.get('skipped', []))}")
                else:
                    log_test("bulk_role_assign", "Bulk assign Asset Manager to 2 users", False, f"Expected updated=2, got {data}")
            else:
                log_test("bulk_role_assign", "Bulk assign Asset Manager to 2 users", False, response=response)
            
            # Test 3: Verify users now have Asset Manager role
            response = admin_session.get(f"{BASE_URL}/admin/users", timeout=15)
            if response.status_code == 200:
                users = response.json()
                ananya_updated = next((u for u in users if u.get("user_id") == ananya_id), None)
                vikram_updated = next((u for u in users if u.get("user_id") == vikram_id), None)
                
                if ananya_updated and ananya_updated.get("role") == "Asset Manager" and vikram_updated and vikram_updated.get("role") == "Asset Manager":
                    log_test("bulk_role_assign", "Verify role changes persisted", True, "Both users now have Asset Manager role")
                else:
                    log_test("bulk_role_assign", "Verify role changes persisted", False, f"ananya role: {ananya_updated.get('role') if ananya_updated else 'not found'}, vikram role: {vikram_updated.get('role') if vikram_updated else 'not found'}")
            else:
                log_test("bulk_role_assign", "Verify role changes persisted", False, response=response)
            
            # Test 4: Try to demote admin's own account (should be skipped)
            if admin_id:
                bulk_payload = {
                    "user_ids": [admin_id],
                    "role": "Student",
                    "status": "Active"
                }
                response = admin_session.post(f"{BASE_URL}/admin/users/bulk-role", json=bulk_payload, timeout=15)
                if response.status_code == 200:
                    data = response.json()
                    if data.get("updated") == 0 and len(data.get("skipped", [])) == 1:
                        skip_reason = data["skipped"][0].get("reason", "")
                        if "own admin access" in skip_reason or "admin" in skip_reason.lower():
                            log_test("bulk_role_assign", "Admin self-demotion protection", True, f"Correctly skipped with reason: {skip_reason}")
                        else:
                            log_test("bulk_role_assign", "Admin self-demotion protection", False, f"Skipped but wrong reason: {skip_reason}")
                    else:
                        log_test("bulk_role_assign", "Admin self-demotion protection", False, f"Expected updated=0, skipped=1, got {data}")
                else:
                    log_test("bulk_role_assign", "Admin self-demotion protection", False, response=response)
            
            # Test 5: Try unknown role (should get 400)
            bulk_payload = {
                "user_ids": [ananya_id],
                "role": "SuperKing",
                "status": "Active"
            }
            response = admin_session.post(f"{BASE_URL}/admin/users/bulk-role", json=bulk_payload, timeout=15)
            if response.status_code == 400:
                log_test("bulk_role_assign", "Unknown role validation", True, "Correctly rejected with 400")
            else:
                log_test("bulk_role_assign", "Unknown role validation", False, f"Expected 400, got {response.status_code}")
            
            # Test 6: Cleanup - set test users back to Student
            bulk_payload = {
                "user_ids": [ananya_id, vikram_id],
                "role": "Student",
                "status": "Active"
            }
            response = admin_session.post(f"{BASE_URL}/admin/users/bulk-role", json=bulk_payload, timeout=15)
            if response.status_code == 200:
                log_test("bulk_role_assign", "Cleanup: Reset users to Student", True, "Users reset successfully")
            else:
                log_test("bulk_role_assign", "Cleanup: Reset users to Student", False, response=response)
            
        else:
            log_test("bulk_role_assign", "GET /admin/users", False, response=response)
    except Exception as e:
        log_test("bulk_role_assign", "GET /admin/users", False, f"Exception: {str(e)}")
    
    # Test 7: Try as Asset Manager (non-admin) - should get 403
    am_session = login(ASSET_MANAGER_EMAIL, ASSET_MANAGER_PASSWORD)
    if am_session:
        bulk_payload = {
            "user_ids": ["dummy_id"],
            "role": "Student",
            "status": "Active"
        }
        response = am_session.post(f"{BASE_URL}/admin/users/bulk-role", json=bulk_payload, timeout=15)
        if response.status_code == 403:
            log_test("bulk_role_assign", "Non-admin access control (403)", True, "Correctly rejected Asset Manager with 403")
        else:
            log_test("bulk_role_assign", "Non-admin access control (403)", False, f"Expected 403, got {response.status_code}")
    else:
        log_test("bulk_role_assign", "Non-admin access control (403)", False, "Could not login as Asset Manager")

def test_unified_search():
    """Test unified search endpoint"""
    print("\n" + "="*80)
    print("TESTING: UNIFIED SEARCH - GET /search")
    print("="*80)
    
    # Login as Admin
    admin_session = login(ADMIN_EMAIL, ADMIN_PASSWORD)
    if not admin_session:
        log_test("unified_search", "Admin login", False, "Cannot proceed with tests")
        return
    
    # Test 1: Search for "projector" as Admin (should return assets)
    try:
        response = admin_session.get(f"{BASE_URL}/search?q=projector", timeout=15)
        if response.status_code == 200:
            data = response.json()
            if "assets" in data and "maintenance" in data and "bookings" in data and "users" in data:
                if len(data["assets"]) > 0:
                    log_test("unified_search", "Admin search 'projector' returns assets", True, f"Found {len(data['assets'])} assets (e.g., {data['assets'][0].get('name', 'N/A')})")
                else:
                    log_test("unified_search", "Admin search 'projector' returns assets", False, "No assets found (may be data issue)")
            else:
                log_test("unified_search", "Admin search 'projector' structure", False, f"Missing expected keys in response: {list(data.keys())}")
        else:
            log_test("unified_search", "Admin search 'projector'", False, response=response)
    except Exception as e:
        log_test("unified_search", "Admin search 'projector'", False, f"Exception: {str(e)}")
    
    # Test 2: Search for "ananya" as Admin (should return users)
    try:
        response = admin_session.get(f"{BASE_URL}/search?q=ananya", timeout=15)
        if response.status_code == 200:
            data = response.json()
            if len(data.get("users", [])) > 0:
                user = data["users"][0]
                log_test("unified_search", "Admin search 'ananya' returns users", True, f"Found {len(data['users'])} user(s): {user.get('name', 'N/A')} ({user.get('email', 'N/A')})")
            else:
                log_test("unified_search", "Admin search 'ananya' returns users", False, "No users found")
        else:
            log_test("unified_search", "Admin search 'ananya'", False, response=response)
    except Exception as e:
        log_test("unified_search", "Admin search 'ananya'", False, f"Exception: {str(e)}")
    
    # Test 3: Search for "ananya" as Asset Manager (users should be empty)
    am_session = login(ASSET_MANAGER_EMAIL, ASSET_MANAGER_PASSWORD)
    if am_session:
        try:
            response = am_session.get(f"{BASE_URL}/search?q=ananya", timeout=15)
            if response.status_code == 200:
                data = response.json()
                if len(data.get("users", [])) == 0:
                    log_test("unified_search", "Asset Manager search 'ananya' - users hidden", True, "Users array correctly empty for non-admin")
                else:
                    log_test("unified_search", "Asset Manager search 'ananya' - users hidden", False, f"Users should be empty but got {len(data['users'])} users")
                
                # Verify other arrays still work
                if "assets" in data and "maintenance" in data and "bookings" in data:
                    log_test("unified_search", "Asset Manager search - other arrays present", True, "assets/maintenance/bookings arrays present")
                else:
                    log_test("unified_search", "Asset Manager search - other arrays present", False, f"Missing arrays: {list(data.keys())}")
            else:
                log_test("unified_search", "Asset Manager search 'ananya'", False, response=response)
        except Exception as e:
            log_test("unified_search", "Asset Manager search 'ananya'", False, f"Exception: {str(e)}")
    else:
        log_test("unified_search", "Asset Manager login", False, "Could not login as Asset Manager")
    
    # Test 4: Empty search (should return empty arrays)
    try:
        response = admin_session.get(f"{BASE_URL}/search?q=", timeout=15)
        if response.status_code == 200:
            data = response.json()
            if (len(data.get("assets", [])) == 0 and 
                len(data.get("users", [])) == 0 and 
                len(data.get("bookings", [])) == 0 and 
                len(data.get("maintenance", [])) == 0):
                log_test("unified_search", "Empty search returns empty arrays", True, "All arrays empty as expected")
            else:
                log_test("unified_search", "Empty search returns empty arrays", False, f"Expected all empty, got assets:{len(data.get('assets',[]))}, users:{len(data.get('users',[]))}, bookings:{len(data.get('bookings',[]))}, maintenance:{len(data.get('maintenance',[]))}")
        else:
            log_test("unified_search", "Empty search", False, response=response)
    except Exception as e:
        log_test("unified_search", "Empty search", False, f"Exception: {str(e)}")

def test_extended_create_fields():
    """Test extended fields in asset and maintenance creation"""
    print("\n" + "="*80)
    print("TESTING: EXTENDED CREATE FIELDS - POST /assets and POST /maintenance")
    print("="*80)
    
    # Login as Admin
    admin_session = login(ADMIN_EMAIL, ADMIN_PASSWORD)
    if not admin_session:
        log_test("extended_create_fields", "Admin login", False, "Cannot proceed with tests")
        return
    
    # Test 1: Create asset with all extended fields
    asset_payload = {
        "name": "Test Projector XYZ",
        "category": "IT Equipment",
        "location": "Conference Room A",
        "department": "IT Department",
        "status": "Available",
        "serial": "PROJ-2025-XYZ-789",
        "bookable": True,
        "supplier": "Acme Electronics Ltd",
        "purchase_cost": 1250.50,
        "purchase_date": "2025-01-10",
        "warranty_end": "2027-01-10",
        "amc_provider": "Acme AMC Services",
        "notes": "High-resolution projector for presentations and training sessions"
    }
    
    try:
        response = admin_session.post(f"{BASE_URL}/assets", json=asset_payload, timeout=15)
        if response.status_code == 200:
            data = response.json()
            # Verify all extended fields are present in response
            checks = {
                "supplier": data.get("supplier") == "Acme Electronics Ltd",
                "purchase_cost": data.get("purchase_cost") == 1250.50,
                "purchase_date": data.get("purchase_date") == "2025-01-10",
                "warranty_end": data.get("warranty_end") == "2027-01-10",
                "amc_provider": data.get("amc_provider") == "Acme AMC Services",
                "notes": data.get("notes") == "High-resolution projector for presentations and training sessions",
                "bookable": data.get("bookable") == True,
                "serial": data.get("serial") == "PROJ-2025-XYZ-789"
            }
            
            all_passed = all(checks.values())
            failed_fields = [k for k, v in checks.items() if not v]
            
            if all_passed:
                log_test("extended_create_fields", "POST /assets with extended fields", True, f"All extended fields present: supplier, purchase_cost (1250.5), warranty_end, amc_provider, notes, bookable, serial")
            else:
                log_test("extended_create_fields", "POST /assets with extended fields", False, f"Missing or incorrect fields: {failed_fields}. Response: {json.dumps(data, indent=2)[:500]}")
            
            # Store asset_id for cleanup
            created_asset_id = data.get("asset_id")
            
        else:
            log_test("extended_create_fields", "POST /assets with extended fields", False, response=response)
            created_asset_id = None
    except Exception as e:
        log_test("extended_create_fields", "POST /assets with extended fields", False, f"Exception: {str(e)}")
        created_asset_id = None
    
    # Test 2: Create maintenance with extended fields
    # First, get an existing asset to use
    try:
        response = admin_session.get(f"{BASE_URL}/assets", timeout=15)
        if response.status_code == 200:
            assets = response.json()
            if len(assets) > 0:
                test_asset_id = assets[0].get("asset_id")
                
                maintenance_payload = {
                    "asset_id": test_asset_id,
                    "description": "Electrical fault in power supply unit - intermittent shutdowns",
                    "priority": "Medium",
                    "category": "Electrical",
                    "location": "Lab 1 - Computer Science Building",
                    "reporter_contact": "9998887777"
                }
                
                response = admin_session.post(f"{BASE_URL}/maintenance", json=maintenance_payload, timeout=15)
                if response.status_code == 200:
                    data = response.json()
                    # Verify extended fields
                    checks = {
                        "category": data.get("category") == "Electrical",
                        "location": data.get("location") == "Lab 1 - Computer Science Building",
                        "reporter_contact": data.get("reporter_contact") == "9998887777",
                        "description": data.get("description") == "Electrical fault in power supply unit - intermittent shutdowns",
                        "priority": data.get("priority") == "Medium"
                    }
                    
                    all_passed = all(checks.values())
                    failed_fields = [k for k, v in checks.items() if not v]
                    
                    if all_passed:
                        log_test("extended_create_fields", "POST /maintenance with extended fields", True, f"All extended fields present: category (Electrical), location (Lab 1), reporter_contact (9998887777)")
                    else:
                        log_test("extended_create_fields", "POST /maintenance with extended fields", False, f"Missing or incorrect fields: {failed_fields}. Response: {json.dumps(data, indent=2)[:500]}")
                else:
                    log_test("extended_create_fields", "POST /maintenance with extended fields", False, response=response)
            else:
                log_test("extended_create_fields", "POST /maintenance - get asset", False, "No assets found in database")
        else:
            log_test("extended_create_fields", "POST /maintenance - get asset", False, response=response)
    except Exception as e:
        log_test("extended_create_fields", "POST /maintenance with extended fields", False, f"Exception: {str(e)}")

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
        
        status = "✅ ALL PASSED" if failed == 0 else f"❌ {failed} FAILED"
        print(f"\n{feature.upper().replace('_', ' ')}: {passed}/{total} passed {status}")
        
        # Print failed tests
        if failed > 0:
            print("  Failed tests:")
            for detail in results["details"]:
                if "❌ FAIL" in detail:
                    print(f"    {detail}")
    
    print("\n" + "="*80)
    print(f"OVERALL: {total_passed}/{total_passed + total_failed} tests passed")
    if total_failed == 0:
        print("✅ ALL TESTS PASSED")
    else:
        print(f"❌ {total_failed} TESTS FAILED")
    print("="*80)
    
    return total_failed == 0

def main():
    """Run all tests"""
    print("="*80)
    print("AssetFlow Campus Backend API Testing - New Features")
    print("Testing: Bulk role assign, Unified search, Extended create fields")
    print("="*80)
    
    test_bulk_role_assign()
    test_unified_search()
    test_extended_create_fields()
    
    all_passed = print_summary()
    
    sys.exit(0 if all_passed else 1)

if __name__ == "__main__":
    main()
