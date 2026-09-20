/* Run with the already installed Playwright via PLAYWRIGHT_MODULE. */
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const assert = require('node:assert/strict');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const root = path.resolve(__dirname, '..');
(async () => {
  const browser = await chromium.launch({ channel: 'chrome', headless: true });
  try {
    const context = await browser.newContext({ offline: true, viewport: { width: 375, height: 900 } });
    const page = await context.newPage();
    const errors = [], external = [];
    page.on('pageerror', e => errors.push(e.message));
    page.on('request', r => { if (/^https?:/.test(r.url())) external.push(r.url()); });
    await page.goto(pathToFileURL(path.join(root, 'index.html')).href);
    const boxes = page.locator('input[type="checkbox"]');
    assert.equal(await boxes.count(), 96);
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    for (const box of await boxes.all()) {
      const size = await box.boundingBox();
      assert.ok(size.width >= 28 && size.height >= 28, JSON.stringify(size));
    }
    await boxes.first().check();
    await boxes.nth(41).check();
    await boxes.last().check();
    assert.equal(await page.locator('#completion-security-count').innerText(), '資安 1/41');
    assert.equal(await page.locator('#completion-ai-count').innerText(), 'AI 2/55');
    const style = await page.locator('tr.is-complete td').first().evaluate(el => ({ opacity: getComputedStyle(el).opacity, decoration: getComputedStyle(el).textDecorationLine }));
    assert.ok(Number(style.opacity) < 1);
    assert.match(style.decoration, /line-through/);
    await page.reload();
    assert.equal(await page.locator('input:checked').count(), 3);
    await page.evaluate(() => Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText: async value => { window.copiedCode = value; } } }));
    await page.locator('#copy-progress').click();
    const code = await page.evaluate(() => window.copiedCode);
    assert.equal(code.length, 38);
    await boxes.nth(1).check();
    page.once('dialog', d => d.accept(code));
    await page.locator('#paste-progress').click();
    assert.equal(await page.locator('input:checked').count(), 4);
    page.once('dialog', d => d.accept('invalid-code'));
    await page.locator('#paste-progress').click();
    assert.equal(await page.locator('input:checked').count(), 4);
    page.once('dialog', d => d.dismiss());
    await page.locator('#clear-progress').click();
    assert.equal(await page.locator('input:checked').count(), 4);
    await page.evaluate(() => localStorage.setItem('unrelated', 'keep'));
    page.once('dialog', d => d.accept());
    await page.locator('#clear-progress').click();
    assert.equal(await page.locator('input:checked').count(), 0);
    assert.equal(await page.evaluate(() => localStorage.getItem('unrelated')), 'keep');
    await page.reload();
    assert.equal(await page.locator('input:checked').count(), 0);
    page.once('dialog', d => d.accept(code));
    await page.locator('#paste-progress').click();
    assert.equal(await page.locator('input:checked').count(), 3);
    for (const width of [375, 1440]) {
      await page.setViewportSize({ width, height: 1000 });
      await page.evaluate(() => window.scrollTo({ top: 0, behavior: 'instant' }));
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
      await page.screenshot({ path: path.join(root, `evidence/completion-${width}.png`) });
    }
    await page.setViewportSize({ width: 375, height: 1000 });
    await boxes.first().scrollIntoViewIfNeeded();
    await page.screenshot({ path: path.join(root, 'evidence/completion-rows-375.png') });
    assert.deepEqual(errors, []);
    assert.deepEqual(external, []);
    await context.close();
    console.log('PASS browser: 96 touch targets >=28px at 375px; no overflow at 375/1440px; dim/strike, reload persistence, copy/paste merge, invalid code, confirmed reset; errors=0; external requests=0');
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
