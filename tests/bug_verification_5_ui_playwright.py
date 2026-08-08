"""Playwright steps used by mcp_browser_automation for iteration 5 UI verification.

This file mirrors the script passed to the browser automation tool. It is not meant
to be executed directly; the tool injects an async Playwright `page` object.
"""

SCRIPT = r'''
import os

base = "https://complete-coverage-3.preview.emergentagent.com"
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

async def login_admin():
    await page.set_viewport_size({"width": 1920, "height": 1080})
    await page.goto(base + "/login", wait_until="domcontentloaded")
    await page.locator('[data-testid="auth-email-input"]').fill("admin@assetflow.edu")
    await page.locator('[data-testid="auth-password-input"]').fill("Admin123!")
    await page.locator('[data-testid="auth-submit-button"]').click()
    await page.wait_for_url("**/dashboard", timeout=30000)

async def maintenance_photo_flow():
    seen = []
    page.on("request", lambda req: seen.append(req.method) if "/api/maintenance/mnt_seed_01/photos" in req.url else None)
    page.on("dialog", lambda dialog: dialog.accept())
    await page.goto(base + "/maintenance", wait_until="domcontentloaded")
    card = page.locator('[data-testid="maintenance-request-card"]').filter(has_text="Spindle vibration").first
    await card.wait_for(state="visible", timeout=30000)
    before_imgs = await card.locator('[data-testid="photo-strip"] img').count()
    if before_imgs != 0:
        raise AssertionError(f"expected clean seed card with 0 photos, saw {before_imgs}")
    upload_input = card.locator('[data-testid="maintenance-photo-upload-input"]').first
    async with page.expect_response(lambda res: "/api/maintenance/mnt_seed_01/photos" in res.url and res.request.method == "POST", timeout=90000) as post_info:
        await upload_input.set_input_files({"name": "bugverify-maintenance.png", "mimeType": "image/png", "buffer": png_bytes})
    post_resp = await post_info.value
    if post_resp.status != 200:
        raise AssertionError(f"maintenance photo POST returned {post_resp.status}")
    await page.wait_for_function("""() => {
        const cards = Array.from(document.querySelectorAll('[data-testid="maintenance-request-card"]'));
        const c = cards.find(el => el.textContent.includes('Spindle vibration'));
        return !!c && c.querySelectorAll('[data-testid="photo-strip"] img').length > 0;
    }""", timeout=30000)
    card = page.locator('[data-testid="maintenance-request-card"]').filter(has_text="Spindle vibration").first
    if await card.locator('[data-testid="photo-strip"] img').count() < 1:
        raise AssertionError("thumbnail did not appear after upload")
    async with page.expect_response(lambda res: "/api/maintenance/mnt_seed_01/photos/" in res.url and res.request.method == "DELETE", timeout=60000) as del_info:
        await card.locator('[data-testid="photo-remove-button"]').first.click()
    del_resp = await del_info.value
    if del_resp.status != 200:
        raise AssertionError(f"maintenance photo DELETE returned {del_resp.status}")
    await page.wait_for_function("""() => {
        const cards = Array.from(document.querySelectorAll('[data-testid="maintenance-request-card"]'));
        const c = cards.find(el => el.textContent.includes('Spindle vibration'));
        return !!c && c.querySelectorAll('[data-testid="photo-strip"] img').length === 0;
    }""", timeout=30000)
    if "POST" not in seen or "DELETE" not in seen:
        raise AssertionError(f"did not observe both POST and DELETE requests, saw {seen}")

async def digest_page_flow():
    await page.set_viewport_size({"width": 1920, "height": 1080})
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
    printed = await page.evaluate("window.__printed")
    if not printed:
        raise AssertionError("print button did not call window.print")
    async with page.expect_download(timeout=60000) as download_info:
        await page.locator('[data-testid="digest-download-pdf"]').click()
    download = await download_info.value
    path = await download.path()
    if not path or os.path.getsize(path) < 1000:
        raise AssertionError("PDF download did not produce a non-empty file")
    print(f"Digest row counts: {row_counts}; downloaded {os.path.getsize(path)} bytes")

async def branding_panel_flow():
    await page.set_viewport_size({"width": 1920, "height": 1080})
    await page.goto(base + "/admin", wait_until="domcontentloaded")
    panel = page.locator('[data-testid="branding-panel"]').first
    await panel.wait_for(state="visible", timeout=30000)
    await panel.scroll_into_view_if_needed()
    await panel.locator('[data-testid="branding-name"]').fill("UI Test Institute")
    await panel.locator('[data-testid="branding-tagline"]').fill("Corridor ready")
    await panel.locator('[data-testid="branding-body"]').fill("NAAC QA")
    await panel.locator('[data-testid="branding-footer"]').fill("UI footer")
    await panel.locator('[data-testid="branding-color"]').fill("#123abc")
    await panel.locator('[data-testid="branding-save"]').click()
    await page.wait_for_timeout(1000)
    brand = await page.evaluate("async () => await (await fetch('/api/admin/branding', {credentials:'include'})).json()")
    if brand.get("institution_name") != "UI Test Institute" or brand.get("accent_color") != "#123abc":
        raise AssertionError(f"branding save did not persist expected values: {brand}")
    logo_input = panel.locator('[data-testid="branding-logo-upload-input"]').first
    async with page.expect_response(lambda res: "api.cloudinary.com" in res.url and res.request.method == "POST", timeout=90000) as logo_resp_info:
        await logo_input.set_input_files({"name": "bugverify-logo.png", "mimeType": "image/png", "buffer": png_bytes})
    logo_resp = await logo_resp_info.value
    if logo_resp.status < 200 or logo_resp.status >= 300:
        raise AssertionError(f"Cloudinary logo upload returned {logo_resp.status}")
    await page.wait_for_function("""() => {
        const panel = document.querySelector('[data-testid="branding-panel"]');
        const img = panel && panel.querySelector('img[src*="res.cloudinary.com"]');
        return !!img;
    }""", timeout=30000)
    await panel.locator('[data-testid="branding-save"]').click()
    await page.wait_for_timeout(1000)
    brand = await page.evaluate("async () => await (await fetch('/api/admin/branding', {credentials:'include'})).json()")
    if not brand.get("logo_url", "").startswith("https://res.cloudinary.com/"):
        raise AssertionError(f"logo upload did not save Cloudinary URL: {brand}")

async def qr_mobile_flow():
    await page.set_viewport_size({"width": 390, "height": 844})
    await page.goto(base + "/scan", wait_until="domcontentloaded")
    manual = page.locator('[data-testid="qr-manual-input"]').first
    lookup = page.locator('[data-testid="qr-lookup-button"]').first
    start = page.locator('[data-testid="qr-start-camera"]').first
    await manual.wait_for(state="visible", timeout=30000)
    meta = await page.locator('meta[name="apple-mobile-web-app-capable"]').get_attribute("content")
    if meta != "yes":
        raise AssertionError(f"missing apple mobile capable meta, got {meta}")
    await manual.fill("AF-2025-1001")
    await lookup.click()
    await page.locator('[data-testid="qr-scan-result"]').wait_for(state="visible", timeout=30000)
    result_text = await page.locator('[data-testid="qr-scan-result"]').inner_text()
    if "AF-2025-1001" not in result_text:
        raise AssertionError(f"manual lookup result did not include expected tag: {result_text}")
    boxes = {}
    for name, loc in [("manual input", manual), ("lookup button", lookup), ("start camera button", start)]:
        box = await loc.bounding_box()
        boxes[name] = box
        if not box or box["width"] < 44 or box["height"] < 44:
            raise AssertionError(f"{name} touch target is below 44px: {box}")
    print(f"QR touch target boxes: {boxes}")

try:
    await record("admin login", login_admin)
    await record("maintenance real photo upload and remove", maintenance_photo_flow)
    await record("admin weekly digest UI, print and PDF", digest_page_flow)
    await record("admin NAAC branding editor and logo upload", branding_panel_flow)
    await record("mobile QR manual lookup and touch targets", qr_mobile_flow)

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
    print("ALL UI CHECKS PASSED")
except Exception as exc:
    print(f"UI TEST RUN FAILED: {exc}")
    raise
'''