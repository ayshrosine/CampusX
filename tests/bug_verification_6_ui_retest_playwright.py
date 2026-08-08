"""Focused retest for iteration 6 UI checks that needed more robust selectors/actions."""

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


async def branding_retest():
    await page.goto(base + "/admin", wait_until="domcontentloaded")
    panel = page.locator('[data-testid="branding-panel"]').first
    await panel.wait_for(state="visible", timeout=30000)
    await panel.scroll_into_view_if_needed()
    await panel.locator('[data-testid="branding-name"]').fill("UI6 Retest Institute")
    await panel.locator('[data-testid="branding-tagline"]').fill("Corridor ready retest")
    await panel.locator('[data-testid="branding-body"]').fill("NAAC Retest")
    await panel.locator('[data-testid="branding-footer"]').fill("UI6 retest footer")
    await panel.locator('[data-testid="branding-color"]').fill("#123abc")
    await panel.locator('[data-testid="branding-save"]').click()
    await page.wait_for_timeout(1200)
    brand = await page.evaluate("async () => await (await fetch('/api/admin/branding', {credentials:'include'})).json()")
    if brand.get("institution_name") != "UI6 Retest Institute" or brand.get("accent_color") != "#123abc":
        raise AssertionError(f"branding text/color save failed: {brand}")
    logo_input = panel.locator('[data-testid="branding-logo-upload-input"]').first
    async with page.expect_response(lambda res: "api.cloudinary.com" in res.url and res.request.method == "POST", timeout=90000) as logo_info:
        await logo_input.set_input_files({"name": "bugverify6-retest-logo.png", "mimeType": "image/png", "buffer": png_bytes})
    logo_resp = await logo_info.value
    if logo_resp.status < 200 or logo_resp.status >= 300:
        raise AssertionError(f"Cloudinary logo upload returned {logo_resp.status}")
    await page.wait_for_function("""() => {
        const img = document.querySelector('[data-testid="branding-panel"] img[src*="res.cloudinary.com"]');
        return !!img;
    }""", timeout=30000)
    await panel.locator('[data-testid="branding-save"]').click()
    await page.wait_for_timeout(1200)
    brand = await page.evaluate("async () => await (await fetch('/api/admin/branding', {credentials:'include'})).json()")
    if brand.get("institution_name") != "UI6 Retest Institute" or not brand.get("logo_url", "").startswith("https://res.cloudinary.com/"):
        raise AssertionError(f"branding logo save failed: {brand}")
    async with page.expect_download(timeout=60000) as download_info:
        await page.locator('[data-testid="accreditation-export-pdf"]').click()
    download = await download_info.value
    path = await download.path()
    if not path or os.path.getsize(path) < 1000:
        raise AssertionError("NAAC PDF export was empty")


async def kanban_drag_retest():
    await page.goto(base + "/maintenance", wait_until="domcontentloaded")
    card = page.locator('[data-testid="maintenance-request-card"]').filter(has_text="Spindle vibration").first
    target = page.locator('[data-testid="kanban-column-resolved"]').first
    await card.wait_for(state="visible", timeout=30000)
    await target.wait_for(state="visible", timeout=30000)
    card_box = await card.bounding_box()
    target_box = await target.bounding_box()
    if not card_box or not target_box:
        raise AssertionError(f"missing boxes: card={card_box}, target={target_box}")
    async with page.expect_response(lambda res: "/api/maintenance/mnt_seed_01" in res.url and res.request.method == "PATCH", timeout=90000) as patch_info:
        await page.mouse.move(card_box["x"] + card_box["width"] / 2, card_box["y"] + card_box["height"] / 2)
        await page.mouse.down()
        await page.mouse.move(target_box["x"] + target_box["width"] / 2, target_box["y"] + 120, steps=30)
        await page.mouse.up()
    patch_resp = await patch_info.value
    if patch_resp.status != 200:
        raise AssertionError(f"kanban drag PATCH returned {patch_resp.status}")
    await page.wait_for_function("""() => {
        const col = document.querySelector('[data-testid="kanban-column-resolved"]');
        return !!col && col.textContent.includes('Spindle vibration');
    }""", timeout=30000)


async def role_notifications_retest():
    await page.goto(base + "/dashboard", wait_until="domcontentloaded")
    await page.locator('[data-testid="notifications-button"]').click()
    drawer = page.locator('[data-testid="notifications-drawer"]').first
    await drawer.wait_for(state="visible", timeout=30000)
    if "Notifications" not in await drawer.inner_text():
        raise AssertionError("notifications drawer missing title")
    await page.locator('[aria-label="Close notifications"]').click(force=True)
    await page.locator('[data-testid="open-role-preview"]').click()
    await page.locator('[data-testid="role-preview-modal"]').wait_for(state="visible", timeout=30000)
    await page.locator('[data-testid="role-preview-select"]').select_option("HOD")
    await page.wait_for_timeout(500)
    count = await page.locator('[data-testid="role-visible-page"]').count()
    if count < 1:
        raise AssertionError(f"role playground visible pages count={count}")
    await page.locator('[data-testid="role-preview-close"]').click(force=True)
    await page.locator('[data-testid="role-preview-modal"]').wait_for(state="hidden", timeout=30000)


async def rbac_blank_retest():
    await page.locator('[data-testid="logout-button"]').click(force=True)
    await page.wait_for_url("**/login", timeout=30000)
    await login("demo@assetflow.edu", "Campus123!")
    if await page.locator('[data-testid="nav-weekly-digest"]').count() != 0:
        raise AssertionError("non-admin user can see Weekly Digest nav")
    status = await page.evaluate("async () => (await fetch('/api/digest/weekly', {credentials:'include'})).status")
    if status != 403:
        raise AssertionError(f"non-admin digest API status should be 403, got {status}")
    await page.locator('[data-testid="logout-button"]').click(force=True)
    await page.wait_for_url("**/login", timeout=30000)
    await page.locator('[data-testid="auth-mode-toggle-button"]').click()
    await page.locator('[data-testid="signup-name-input"]').fill("")
    await page.locator('[data-testid="auth-email-input"]').fill("blankname6@example.edu")
    await page.locator('[data-testid="auth-password-input"]').fill("Campus123!")
    await page.locator('[data-testid="auth-submit-button"]').click()
    valid = await page.locator('[data-testid="signup-name-input"]').evaluate("el => el.checkValidity()")
    if valid:
        raise AssertionError("blank-name signup validator did not reject empty name")


try:
    await record("admin login", login)
    await record("branding text/logo/PDF retest", branding_retest)
    await record("kanban mouse drag-drop retest", kanban_drag_retest)
    await record("notifications and role playground retest", role_notifications_retest)
    await record("RBAC and blank-name validator retest", rbac_blank_retest)

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
    print("ALL ITERATION 6 UI RETEST CHECKS PASSED")
except Exception as exc:
    print(f"ITERATION 6 UI RETEST FAILED: {exc}")
    raise
'''