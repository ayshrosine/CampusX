"""Playwright snippet executed via mcp_browser_automation for iteration 6 UI verification."""


async def run(page):
    await page.set_viewport_size({"width": 1920, "height": 1080})
    await page.wait_for_selector('[data-testid="auth-email-input"]', timeout=15000)
    await page.fill('[data-testid="auth-email-input"]', 'admin@assetflow.edu')
    await page.fill('[data-testid="auth-password-input"]', 'Admin123!')
    await page.click('[data-testid="auth-submit-button"]')
    await page.wait_for_url('**/dashboard', timeout=20000)

    await page.goto('https://fluid-layout-pro.preview.emergentagent.com/admin')
    await page.wait_for_selector('[data-testid="delegations-panel"]', timeout=20000)
    await page.wait_for_selector('[data-testid="bulk-import-panel"]', timeout=10000)
    for selector in [
        '[data-testid="delegation-deputy"]',
        '[data-testid="delegation-start"]',
        '[data-testid="delegation-end"]',
        '[data-testid="delegation-note"]',
        '[data-testid="delegation-create"]',
        '[data-testid="bulk-kind"]',
        '[data-testid="bulk-file"]',
        '[data-testid="bulk-upload"]',
    ]:
        assert await page.locator(selector).count() >= 1

    await page.click('[data-testid="notifications-button"]')
    await page.wait_for_selector('[data-testid="notifications-drawer"]', timeout=10000)
    assert await page.locator('[data-testid="enable-push-button"]').count() >= 1
    await page.click('[data-testid="enable-push-button"]')
    await page.wait_for_timeout(2000)
    registration_exists = await page.evaluate("""async () => {
        if (!('serviceWorker' in navigator)) return false;
        const reg = await navigator.serviceWorker.getRegistration();
        return !!reg;
    }""")
    page_text = await page.locator('body').inner_text()
    assert registration_exists or ('denied' in page_text.lower()) or ('not supported' in page_text.lower()) or ('enabled' in page_text.lower())

    await page.goto('https://fluid-layout-pro.preview.emergentagent.com/audits')
    await page.wait_for_timeout(2500)
    if await page.locator('[data-testid="audit-download-pdf"]').count() < 1:
        await page.fill('[data-testid="audit-department-input"]', 'TEST_UI_ITER6_AuditDept')
        await page.fill('[data-testid="audit-period-input"]', 'July 2026 UI')
        await page.click('[data-testid="audit-create-button"]')
        await page.wait_for_selector('[data-testid="audit-download-pdf"]', timeout=15000)
    assert await page.locator('[data-testid="audit-download-pdf"]').count() >= 1