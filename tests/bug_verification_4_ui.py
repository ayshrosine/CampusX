"""Playwright script body for focused AssetFlow maintenance UI verification.

This file mirrors the script executed through mcp_browser_automation.
It assumes it is run inside an async function with a Playwright `page` object.
"""

import asyncio


async def run(page):
    try:
        print("UI TEST: start")
        await page.set_viewport_size({"width": 1920, "height": 1080})
        page.on("dialog", lambda dialog: asyncio.create_task(dialog.accept()))

        await page.goto("https://complete-coverage-3.preview.emergentagent.com/login", wait_until="domcontentloaded")
        await page.wait_for_timeout(800)
        if await page.locator('[data-testid="auth-email-input"]').is_visible():
            await page.locator('[data-testid="auth-email-input"]').fill("admin@assetflow.edu")
            await page.locator('[data-testid="auth-password-input"]').fill("Admin123!")
            await page.locator('[data-testid="auth-submit-button"]').click()
        await page.wait_for_url("**/dashboard", timeout=15000)
        print("PASS: admin login reached dashboard")

        # Notifications drawer regression.
        await page.locator('[data-testid="notifications-button"]').click()
        await page.wait_for_selector('[data-testid="notifications-drawer"]', timeout=8000)
        print("PASS: notifications drawer opens")
        await page.locator('[data-testid="notifications-drawer"] button[aria-label="Close notifications"]').click(force=True)
        await page.locator('[data-testid="notifications-drawer"]').wait_for(state="detached", timeout=8000)

        # Role playground regression.
        await page.locator('[data-testid="open-role-preview"]').click()
        await page.wait_for_selector('[data-testid="role-preview-modal"]', timeout=8000)
        await page.locator('[data-testid="role-preview-select"]').select_option("Student")
        await page.locator('[data-testid="role-preview-modal"]').get_by_text("Maintenance", exact=True).wait_for(timeout=8000)
        await page.locator('[data-testid="role-preview-close"]').click()
        print("PASS: role preview modal opens and loads Student data")

        # Maintenance menu, status actions, rejected section.
        await page.locator('[data-testid="nav-maintenance"]').click()
        await page.wait_for_url("**/maintenance", timeout=10000)
        await page.wait_for_selector('[data-testid="maintenance-new-request-button"]', timeout=10000)
        suffix = str(int(__import__("time").time() * 1000))
        desc1 = f"TEST_BUG4_UI_MENU_{suffix}"
        desc2 = f"TEST_BUG4_UI_REJECT_{suffix}"
        desc3 = f"TEST_BUG4_UI_DND_{suffix}"

        async def create_request(desc):
            await page.locator('[data-testid="maintenance-new-request-button"]').click()
            await page.locator('[data-testid="maintenance-asset-id-input"]').fill("ast_seed_2")
            await page.locator('[data-testid="maintenance-description-input"]').fill(desc)
            await page.locator('[data-testid="maintenance-priority-select"]').select_option("High")
            async with page.expect_response(lambda r: "/api/maintenance" in r.url and r.request.method == "POST") as resp_info:
                await page.locator('[data-testid="maintenance-submit-button"]').click()
            resp = await resp_info.value
            if resp.status != 200:
                raise Exception(f"Create maintenance failed with {resp.status}")
            await page.wait_for_selector(f'text="{desc}"', timeout=10000)
            print(f"PASS: created maintenance request {desc}")

        async def card_for(desc):
            card = page.locator('[data-testid="maintenance-request-card"]').filter(has_text=desc).first
            await card.wait_for(timeout=10000)
            return card

        await create_request(desc1)
        card = await card_for(desc1)
        await card.locator('[data-testid="maintenance-menu-button"]').click()
        await page.wait_for_selector('[data-testid="maintenance-menu-popover"]', timeout=5000)
        for testid in ["menu-move-next", "menu-move-resolved", "menu-reject", "menu-delete"]:
            if not await page.locator(f'[data-testid="{testid}"]').is_visible():
                raise Exception(f"Maintenance menu missing {testid}")
        print("PASS: maintenance menu shows Move next / Mark resolved / Reject / Delete options")
        async with page.expect_response(lambda r: "/api/maintenance/" in r.url and r.request.method == "PATCH") as patch1:
            await page.locator('[data-testid="menu-move-next"]').click()
        if (await patch1.value).status != 200:
            raise Exception("Move to next PATCH did not return 200")
        await page.locator('[data-testid="kanban-column-approved"]').filter(has_text=desc1).wait_for(timeout=10000)
        print("PASS: Move to next stage sends PATCH and card appears in Approved")

        card = await card_for(desc1)
        await card.locator('[data-testid="maintenance-menu-button"]').click()
        async with page.expect_response(lambda r: "/api/maintenance/" in r.url and r.request.method == "PATCH") as patch2:
            await page.locator('[data-testid="menu-move-resolved"]').click()
        if (await patch2.value).status != 200:
            raise Exception("Mark resolved PATCH did not return 200")
        await page.locator('[data-testid="kanban-column-resolved"]').filter(has_text=desc1).wait_for(timeout=10000)
        print("PASS: Mark resolved sends PATCH and card appears in Resolved")

        await create_request(desc2)
        card = await card_for(desc2)
        await card.locator('[data-testid="maintenance-menu-button"]').click()
        async with page.expect_response(lambda r: "/api/maintenance/" in r.url and r.request.method == "PATCH") as patch3:
            await page.locator('[data-testid="menu-reject"]').click()
        if (await patch3.value).status != 200:
            raise Exception("Reject PATCH did not return 200")
        rejected_section = page.locator("section.surface").filter(has_text="Closed without action").filter(has_text=desc2)
        await rejected_section.wait_for(timeout=10000)
        if not await rejected_section.get_by_text("Reopen", exact=True).is_visible():
            raise Exception("Rejected section missing Reopen button")
        print("PASS: rejected request appears in separate rejected section with Reopen")
        async with page.expect_response(lambda r: "/api/maintenance/" in r.url and r.request.method == "PATCH") as patch4:
            await rejected_section.get_by_text("Reopen", exact=True).click()
        if (await patch4.value).status != 200:
            raise Exception("Rejected Reopen PATCH did not return 200")
        await page.locator('[data-testid="kanban-column-pending"]').filter(has_text=desc2).wait_for(timeout=10000)
        print("PASS: rejected request can be reopened to Pending")

        await create_request(desc3)
        dnd_card = await card_for(desc3)
        target = page.locator('[data-testid="kanban-column-in-progress"]')
        src_box = await dnd_card.bounding_box()
        dst_box = await target.bounding_box()
        if not src_box or not dst_box:
            raise Exception("Missing drag/drop bounding boxes")
        async with page.expect_response(lambda r: "/api/maintenance/" in r.url and r.request.method == "PATCH") as patch_dnd:
            await page.mouse.move(src_box["x"] + src_box["width"] / 2, src_box["y"] + src_box["height"] / 2)
            await page.mouse.down()
            await page.wait_for_timeout(500)
            await page.mouse.move(src_box["x"] + src_box["width"] / 2 + 20, src_box["y"] + src_box["height"] / 2 + 10, steps=5)
            await page.wait_for_timeout(500)
            await page.mouse.move(dst_box["x"] + dst_box["width"] / 2, dst_box["y"] + 110, steps=25)
            await page.wait_for_timeout(500)
            await page.mouse.up()
        if (await patch_dnd.value).status != 200:
            raise Exception("Drag-and-drop PATCH did not return 200")
        await page.locator('[data-testid="kanban-column-in-progress"]').filter(has_text=desc3).wait_for(timeout=10000)
        print("PASS: drag-and-drop moved Pending card to In progress and PATCH fired")

        # UI report downloads regression: verify both buttons initiate downloads.
        await page.locator('[data-testid="nav-reports"]').click()
        await page.wait_for_url("**/reports", timeout=10000)
        async with page.expect_download(timeout=15000) as dl1:
            await page.locator('[data-testid="report-download-csv"]').click()
        csv_download = await dl1.value
        if not csv_download.suggested_filename.endswith(".csv"):
            raise Exception("CSV download filename incorrect")
        async with page.expect_download(timeout=15000) as dl2:
            await page.locator('[data-testid="report-download-pdf"]').click()
        pdf_download = await dl2.value
        if not pdf_download.suggested_filename.endswith(".pdf"):
            raise Exception("PDF download filename incorrect")
        print("PASS: report CSV and PDF download buttons initiate files")

        # QR manual lookup regression.
        await page.locator('[data-testid="scan-nav-button"]').click()
        await page.wait_for_url("**/scan", timeout=10000)
        await page.locator('[data-testid="qr-manual-input"]').fill("AF-2025-1001")
        await page.locator('[data-testid="qr-lookup-button"]').click()
        await page.wait_for_selector('[data-testid="qr-scan-result"]', timeout=10000)
        print("PASS: QR manual lookup returns an asset")

        # Mobile responsive checks.
        await page.set_viewport_size({"width": 390, "height": 844})
        await page.goto("https://complete-coverage-3.preview.emergentagent.com/dashboard", wait_until="domcontentloaded")
        await page.wait_for_selector('[data-testid="mobile-menu-button"]', timeout=10000)
        if not await page.locator('[data-testid="mobile-menu-button"]').is_visible():
            raise Exception("Mobile hamburger not visible")
        await page.locator('[data-testid="mobile-menu-button"]').click()
        sidebar_class = await page.locator('[data-testid="sidebar"]').get_attribute("class")
        if "open" not in (sidebar_class or ""):
            raise Exception("Mobile hamburger did not open sidebar")
        await page.locator('[data-testid="nav-maintenance"]').click()
        await page.wait_for_url("**/maintenance", timeout=10000)
        box = await page.locator('[data-testid="maintenance-new-request-button"]').bounding_box()
        if not box or box["height"] < 44:
            raise Exception(f"Mobile primary button touch target too small: {box}")
        print("PASS: mobile header hamburger opens sidebar and primary touch target is >=44px")

        error_text = await page.evaluate("""() => {
        const errorElements = Array.from(document.querySelectorAll('.error, [class*="error"], [id*="error"]'));
        return errorElements.map(el => el.textContent).join(", ");
        }""")
        if error_text:
            print(f"Found error message: {error_text}")
        else:
            print("No error messages found on the page")
        print("UI TEST: SUCCESS")
    except Exception as e:
        print(f"UI TEST: FAILURE: {e}")
        error_text = await page.evaluate("""() => {
        const errorElements = Array.from(document.querySelectorAll('.error, [class*="error"], [id*="error"]'));
        return errorElements.map(el => el.textContent).join(", ");
        }""")
        if error_text:
            print(f"Found error message: {error_text}")
        else:
            print("No error messages found on the page")
        await page.screenshot(path="/app/test_reports/bug_verification_4_ui_failure.jpg", quality=40, full_page=False)
        raise
