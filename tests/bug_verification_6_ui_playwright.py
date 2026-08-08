"""Playwright steps used by mcp_browser_automation for iteration 6 bug verification.

This file mirrors the script passed to the browser automation tool. It focuses on
the previously failing /scan mobile defects plus smoke checks for same-iteration
regressions.
"""

SCRIPT = r'''
import os

base = "https://fluid-layout-pro.preview.emergentagent.com"
failures = []
png_bytes = bytes.fromhex(
    "89504e470d0a1a0a0000000d494844520000000200000002080600000072b60d24"
    "0000001649444154789c6364f8cfc0c0c0f01f8401c4001fdd03fd447ec4d3"
    "0000000049454e44ae426082"
)


async def record(name, func):
    try:
        await func()
        print(f"PASS - {name}")
    except Exception as exc:
        print(f"FAIL - {name}: {exc}")
        failures.append(f"{name}: {exc}")


async def login(email="admin@assetflow.edu", password="Admin123!"):
    await page.set_viewport_size({"width": 1920, "height": 1080})
    await page.goto(base + "/login", wait_until="domcontentloaded")
    await page.locator('[data-testid="auth-email-input"]').fill(email)
    await page.locator('[data-testid="auth-password-input"]').fill(password)
    await page.locator('[data-testid="auth-submit-button"]').click()
    await page.wait_for_url("**/dashboard", timeout=30000)


async def logout_if_possible():
    await page.set_viewport_size({"width": 1920, "height": 1080})
    if await page.locator('[data-testid="logout-button"]').count() > 0:
        await page.locator('[data-testid="logout-button"]').click()
        await page.wait_for_url("**/login", timeout=30000)


async def qr_mobile_flow():
    await page.set_viewport_size({"width": 390, "height": 844})
    await page.goto(base + "/scan", wait_until="domcontentloaded")
    manual = page.locator('[data-testid="qr-manual-input"]').first
    lookup = page.locator('[data-testid="qr-lookup-button"]').first
    await manual.wait_for(state="visible", timeout=30000)

    head = await page.evaluate("""() => ({
        apple: document.querySelector('meta[name="apple-mobile-web-app-capable"]')?.content || null,
        mobile: document.querySelector('meta[name="mobile-web-app-capable"]')?.content || null,
        bar: document.querySelector('meta[name="apple-mobile-web-app-status-bar-style"]')?.content || null,
        title: document.title
    })""")
    expected = {"apple": "yes", "mobile": "yes", "bar": "black-translucent", "title": "AssetFlow Campus"}
    if head != expected:
        raise AssertionError(f"unexpected /scan head metadata: {head}")

    box = await manual.bounding_box()
    if not box or box["height"] < 44:
        raise AssertionError(f"qr-manual-input height below 44px: {box}")

    await manual.fill("AF-2025-1001")
    await lookup.click()
    await page.locator('[data-testid="qr-scan-result"]').wait_for(state="visible", timeout=30000)
    result_text = await page.locator('[data-testid="qr-scan-result"]').inner_text()
    if "AF-2025-1001" not in result_text or "Open detail" not in result_text or "Check out" not in result_text:
        raise AssertionError(f"manual lookup result missing expected tag/actions: {result_text}")
    print(f"QR input bounding box: {box}; result: {result_text.replace(chr(10), ' | ')}")


async def maintenance_photo_flow():
    page.on("dialog", lambda dialog: dialog.accept())
    await page.set_viewport_size({"width": 1920, "height": 1080})
    await page.goto(base + "/maintenance", wait_until="domcontentloaded")
    card = page.locator('[data-testid="maintenance-request-card"]').filter(has_text="Spindle vibration").first
    await card.wait_for(state="visible", timeout=30000)
    upload_input = card.locator('[data-testid="maintenance-photo-upload-input"]').first
    async with page.expect_response(lambda res: "/api/maintenance/mnt_seed_01/photos" in res.url and res.request.method == "POST", timeout=90000) as post_info:
        await upload_input.set_input_files({"name": "bugverify6-maintenance.png", "mimeType": "image/png", "buffer": png_bytes})
    post_resp = await post_info.value
    if post_resp.status != 200:
        raise AssertionError(f"maintenance photo POST returned {post_resp.status}")
    await card.locator('[data-testid="photo-strip"] img').first.wait_for(state="visible", timeout=30000)
    async with page.expect_response(lambda res: "/api/maintenance/mnt_seed_01/photos/" in res.url and res.request.method == "DELETE", timeout=60000) as del_info:
        await card.locator('[data-testid="photo-remove-button"]').first.click()
    del_resp = await del_info.value
    if del_resp.status != 200:
        raise AssertionError(f"maintenance photo DELETE returned {del_resp.status}")


async def audit_photo_flow():
    await page.goto(base + "/audits", wait_until="domcontentloaded")
    row = page.locator('[data-testid="audit-item-row"]').first
    await row.wait_for(state="visible", timeout=30000)
    upload_input = row.locator('[data-testid="audit-photo-upload-input"]').first
    async with page.expect_response(lambda res: "/api/audits/" in res.url and "/photos" in res.url and res.request.method == "POST", timeout=90000) as post_info:
        await upload_input.set_input_files({"name": "bugverify6-audit.png", "mimeType": "image/png", "buffer": png_bytes})
    post_resp = await post_info.value
    if post_resp.status != 200:
        raise AssertionError(f"audit photo POST returned {post_resp.status}")
    await row.locator('[data-testid="photo-strip"] img').first.wait_for(state="visible", timeout=30000)


async def digest_flow():
    await page.goto(base + "/digest", wait_until="domcontentloaded")
    for tid in ["digest-metric-open-maintenance", "digest-metric-resolved-this-week", "digest-metric-pending-approvals", "digest-metric-utilization"]:
        await page.locator(f'[data-testid="{tid}"]').wait_for(state="visible", timeout=30000)
    row_counts = {}
    for tid in ["digest-maintenance-row", "digest-pending-user", "digest-booking-row", "digest-audit-row"]:
        row_counts[tid] = await page.locator(f'[data-testid="{tid}"]').count()
        if row_counts[tid] < 1:
            raise AssertionError(f"expected at least one {tid}, counts={row_counts}")
    await page.evaluate("window.__printed=false; window.print=()=>{ window.__printed=true; }")
    await page.locator('[data-testid="digest-print"]').click()
    if not await page.evaluate("window.__printed"):
        raise AssertionError("digest print did not call window.print")
    async with page.expect_download(timeout=60000) as download_info:
        await page.locator('[data-testid="digest-download-pdf"]').click()
    download = await download_info.value
    path = await download.path()
    if not path or os.path.getsize(path) < 1000:
        raise AssertionError("digest PDF download was empty")
    print(f"Digest row counts: {row_counts}; PDF bytes={os.path.getsize(path)}")


async def branding_and_pdf_flow():
    await page.goto(base + "/admin", wait_until="domcontentloaded")
    panel = page.locator('[data-testid="branding-panel"]').first
    await panel.wait_for(state="visible", timeout=30000)
    await panel.scroll_into_view_if_needed()
    await panel.locator('[data-testid="branding-name"]').fill("UI6 Test Institute")
    await panel.locator('[data-testid="branding-tagline"]').fill("Corridor ready")
    await panel.locator('[data-testid="branding-body"]').fill("NAAC QA")
    await panel.locator('[data-testid="branding-footer"]').fill("UI6 footer")
    await panel.locator('[data-testid="branding-color"]').fill("#123abc")
    logo_input = panel.locator('[data-testid="branding-logo-upload-input"]').first
    async with page.expect_response(lambda res: "api.cloudinary.com" in res.url and res.request.method == "POST", timeout=90000) as logo_info:
        await logo_input.set_input_files({"name": "bugverify6-logo.png", "mimeType": "image/png", "buffer": png_bytes})
    logo_resp = await logo_info.value
    if logo_resp.status < 200 or logo_resp.status >= 300:
        raise AssertionError(f"Cloudinary logo upload returned {logo_resp.status}")
    await panel.locator('[data-testid="branding-save"]').click()
    await page.wait_for_timeout(1000)
    brand = await page.evaluate("async () => await (await fetch('/api/admin/branding', {credentials:'include'})).json()")
    if brand.get("institution_name") != "UI6 Test Institute" or not brand.get("logo_url", "").startswith("https://res.cloudinary.com/"):
        raise AssertionError(f"branding did not persist expected values: {brand}")
    async with page.expect_download(timeout=60000) as download_info:
        await page.locator('[data-testid="accreditation-export-pdf"]').click()
    download = await download_info.value
    path = await download.path()
    if not path or os.path.getsize(path) < 1000:
        raise AssertionError("admin accreditation PDF was empty")


async def kanban_drag_drop_flow():
    await page.goto(base + "/maintenance", wait_until="domcontentloaded")
    card = page.locator('[data-testid="maintenance-request-card"]').filter(has_text="Spindle vibration").first
    target = page.locator('[data-testid="kanban-column-resolved"]').first
    await card.wait_for(state="visible", timeout=30000)
    await target.wait_for(state="visible", timeout=30000)
    async with page.expect_response(lambda res: "/api/maintenance/mnt_seed_01" in res.url and res.request.method == "PATCH", timeout=60000) as patch_info:
        await card.drag_to(target)
    patch_resp = await patch_info.value
    if patch_resp.status != 200:
        raise AssertionError(f"kanban drag PATCH returned {patch_resp.status}")
    await page.wait_for_function("""() => {
        const col = document.querySelector('[data-testid="kanban-column-resolved"]');
        return !!col && col.textContent.includes('Spindle vibration');
    }""", timeout=30000)


async def notifications_and_role_playground_flow():
    await page.goto(base + "/dashboard", wait_until="domcontentloaded")
    await page.locator('[data-testid="notifications-button"]').click()
    drawer = page.locator('[data-testid="notifications-drawer"]').first
    await drawer.wait_for(state="visible", timeout=30000)
    txt = await drawer.inner_text()
    if "Notifications" not in txt:
        raise AssertionError(f"notifications drawer did not render title: {txt}")
    await page.locator('[aria-label="Close notifications"]').click()
    await page.locator('[data-testid="open-role-preview"]').click()
    modal = page.locator('[data-testid="role-preview-modal"]').first
    await modal.wait_for(state="visible", timeout=30000)
    await modal.locator('[data-testid="role-preview-select"]').select_option("HOD")
    await page.wait_for_timeout(300)
    if await modal.locator('[data-testid="role-visible-page"]').count() < 1:
        raise AssertionError("role playground did not show visible pages")
    await page.locator('[data-testid="role-preview-close"]').click()


async def rbac_and_blank_name_validator_flow():
    await logout_if_possible()
    await login("demo@assetflow.edu", "Campus123!")
    if await page.locator('[data-testid="nav-weekly-digest"]').count() != 0:
        raise AssertionError("Asset Manager should not see Weekly Digest nav")
    status = await page.evaluate("async () => (await fetch('/api/digest/weekly', {credentials:'include'})).status")
    if status != 403:
        raise AssertionError(f"non-admin digest API status should be 403, got {status}")
    await logout_if_possible()
    await page.goto(base + "/login", wait_until="domcontentloaded")
    await page.locator('[data-testid="auth-mode-toggle-button"]').click()
    await page.locator('[data-testid="signup-name-input"]').fill("")
    await page.locator('[data-testid="auth-email-input"]').fill("blankname6@example.edu")
    await page.locator('[data-testid="auth-password-input"]').fill("Campus123!")
    await page.locator('[data-testid="auth-submit-button"]').click()
    valid = await page.locator('[data-testid="signup-name-input"]').evaluate("el => el.checkValidity()")
    if valid:
        raise AssertionError("blank signup name should be invalid")


try:
    await record("admin login", login)
    await record("mobile /scan metadata, touch target, and manual lookup", qr_mobile_flow)
    await record("maintenance real photo upload/delete", maintenance_photo_flow)
    await record("audit real photo upload", audit_photo_flow)
    await record("weekly digest preview/print/PDF", digest_flow)
    await record("NAAC branding/logo/PDF cover export", branding_and_pdf_flow)
    await record("kanban drag-drop status update", kanban_drag_drop_flow)
    await record("notifications drawer and role playground", notifications_and_role_playground_flow)
    await record("RBAC and blank-name validator", rbac_and_blank_name_validator_flow)

    # Get error messages using specific selectors
    error_text = await page.evaluate("""() => {
    const errorElements = Array.from(document.querySelectorAll('.error, [class*="error"], [id*="error"]'));
    return errorElements.map(el => el.textContent).join(", ");
    }""")
    if error_text:
        print(f"Found error message: {error_text}")
    else:
        print("No error messages found on the page")

    if failures:
        raise AssertionError("; ".join(failures))
    print("ALL ITERATION 6 UI CHECKS PASSED")
except Exception as exc:
    print(f"ITERATION 6 UI TEST RUN FAILED: {exc}")
    raise
'''