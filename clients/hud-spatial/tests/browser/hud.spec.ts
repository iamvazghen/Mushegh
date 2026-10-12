import { test, expect } from '@playwright/test';

const emptyControl = { stream_id: 'fixture-stream', sequence: 0, commands: [] };
const snapshot = (overrides = {}) => ({
  generated: new Date().toISOString(), assistant: 'Fixture assistant', owner: 'Fixture owner', presence: 'At the desk',
  objectives: [{ text: 'Test objective', project: 'HUD', latest: 'First step complete', awaiting: ['Choose a renderer'], updated: 'today' }],
  working_on: [{ title: 'Test task', elapsed: '1m', note: 'Verifying', kind: 'test' }],
  awaiting_approval: [{ summary: 'Fixture approval', origin: 'test' }],
  systems: { llm: 'fixture-model', fallbacks: 2, brain: 'online' },
  performance: { turns: 12, tool_calls: 24, tool_errors: 1, llm_p50_ms: 150, llm_p95_ms: 250, uptime_s: 60 },
  health: [{ name: 'fixture-health', ok: true }], reliability: [{ name: 'fixture-reliability' }], loops: [{ name: 'fixture-loop' }],
  turns_trace: { test: 'fixture-trace' }, llm_providers: [{ name: 'fixture-provider' }], unattended: { test: 'fixture-unattended', runs: 2, needs_attention: 1 },
  hud_control: emptyControl, ...overrides,
});

test.beforeEach(async ({ page }) => {
  await page.route('**/api/hud.json', route => route.fulfill({ status: 503, contentType: 'application/json', body: '{}' }));
  await page.goto('/');
});

test('only the command surface and spatial grid persist', async ({ page }) => {
  await expect(page.getByRole('search')).toBeVisible();
  await expect(page.getByTestId('workspace-grid')).toBeVisible();
  await expect(page.locator('header, nav, footer, .canvas-rail, .background-dock, .layout-toolbar')).toHaveCount(0);
  await expect(page.locator('[data-visible=true]')).toHaveCount(4);
  await page.getByRole('button', { name: 'Expand 3D inspector', exact: true }).click();
  await expect(page.locator('[data-visible=true]')).toHaveCount(1);
  await page.getByRole('button', { name: 'Restore grid' }).click();
  await expect(page.locator('[data-visible=true]')).toHaveCount(4);
  await page.getByRole('button', { name: 'Background Conversation', exact: true }).click();
  await expect(page.locator('[data-visible=true]')).toHaveCount(3);
  await page.keyboard.press('Control+k');
  const input = page.getByRole('textbox', { name: 'Mushegh command or canvas search' });
  await input.fill('conversation');
  await page.getByRole('button', { name: 'Open Conversation', exact: true }).click();
  await expect(page.locator('[data-visible=true]')).toHaveCount(4);
  await input.fill('split vertical');
  await page.getByRole('button', { name: 'Run HUD command' }).click();
  await expect(page.locator('[data-visible=true]')).toHaveCount(2);
});

test('drag swaps occupied slots and resizing retains displaced peers', async ({ page }) => {
  const a = page.locator('[data-canvas="transcription"]');
  const b = page.locator('[data-canvas="3d_engine"]');
  const readState = () => page.evaluate(() => JSON.parse(localStorage.getItem('openwatari.hud.layout.v1')!));
  const handle = await a.locator('.drag-handle').boundingBox();
  const target = await b.locator('.drag-handle').boundingBox();
  await page.mouse.move(handle!.x + 40, handle!.y + 12); await page.mouse.down();
  await page.mouse.move(target!.x + 40, target!.y + 12, { steps: 20 }); await page.mouse.up();
  await expect.poll(async () => (await readState()).tiles.find((tile: { id: string }) => tile.id === 'transcription').x).toBe(6);
  const input = page.getByRole('textbox', { name: 'Mushegh command or canvas search' });
  await input.fill('reset'); await page.getByRole('button', { name: 'Run HUD command' }).click();
  await expect.poll(async () => (await a.boundingBox())!.x).toBeLessThan(100);
  const corner = a.locator('.react-resizable-handle');
  const box = await corner.boundingBox(); const bounds = await b.boundingBox();
  await page.mouse.move(box!.x + box!.width / 2, box!.y + box!.height / 2); await page.mouse.down();
  await page.mouse.move(bounds!.x + bounds!.width - 6, box!.y + box!.height / 2, { steps: 20 }); await page.mouse.up();
  await expect.poll(async () => (await readState()).tiles.find((tile: { id: string }) => tile.id === 'transcription').w).toBe(12);
  expect((await readState()).background).toContain('3d_engine');
});

test('local document state survives background and restore', async ({ page }) => {
  await page.keyboard.press('Control+k');
  await page.getByRole('textbox', { name: 'Mushegh command or canvas search' }).fill('documents');
  await page.getByRole('button', { name: 'Open Documents', exact: true }).click();
  const pdf = '%PDF-1.1\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 300] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n4 0 obj\n<< /Length 48 >>\nstream\nBT /F1 18 Tf 20 200 Td (HUD fixture document) Tj ET\nendstream\nendobj\n5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF';
  await page.locator('input[type=file][accept="application/pdf"]').setInputFiles({ name: 'test-reference.pdf', mimeType: 'application/pdf', buffer: Buffer.from(pdf) });
  await expect(page.locator('.react-pdf__Page canvas')).toBeVisible();
  await page.getByRole('textbox', { name: 'Highlight on page' }).fill('fixture');
  await expect(page.locator('.react-pdf__Page mark')).toContainText('fixture');
  await page.getByRole('button', { name: 'Background Documents', exact: true }).click();
  await page.keyboard.press('Control+k'); await page.getByRole('textbox', { name: 'Mushegh command or canvas search' }).fill('documents');
  await page.getByRole('button', { name: 'Open Documents', exact: true }).click();
  await expect(page.getByRole('textbox', { name: 'Highlight on page' })).toHaveValue('fixture');
});

test('3D canvas begins empty and renders only after an Mushegh-shaped command', async ({ page }) => {
  const tile = page.locator('[data-canvas="3d_engine"]');
  await expect(tile.getByText('Scene ready for Mushegh')).toBeVisible();
  await expect(tile.locator('canvas')).toHaveCount(0);
  const input = page.getByRole('textbox', { name: 'Mushegh command or canvas search' });
  await input.fill('render sphere'); await page.getByRole('button', { name: 'Run HUD command' }).click();
  await expect(tile.locator('canvas')).toBeVisible({ timeout: 15000 });
  await expect(tile.getByText('SPHERE')).toBeVisible();
  await input.fill('render sphere'); await page.getByRole('button', { name: 'Run HUD command' }).click();
  await expect(page.locator('[data-visible=true]')).toHaveCount(1);
  await page.getByRole('button', { name: 'Clear 3D scene' }).click();
  await expect(tile.getByText('Scene ready for Mushegh')).toBeVisible();
});

test('renders real snapshot fields and consumes a fresh remote command once', async ({ page }) => {
  const issued = new Date().toISOString();
  await page.route('**/api/hud.json', route => route.fulfill({ json: snapshot({ hud_control: { stream_id: 'voice-stream', sequence: 1, commands: [{ sequence: 1, issued_at: issued, action: 'open', canvas: 'agents' }] } }) }));
  await page.reload();
  await expect(page.getByText('Test objective')).toBeVisible();
  await expect(page.locator('[data-canvas="agents"][data-visible=true]')).toBeVisible();
  await expect(page.locator('.command-notice')).toContainText('Mushegh applied: open');
  const d = page.locator('[data-canvas="diagnostics"]');
  for (const name of ['Component health', 'Provider health', 'Background loops', 'Tool reliability', 'Turn trace & token accounting', 'Unattended work & remaining budget', 'All performance values']) await d.locator('summary', { hasText: name }).click();
  await expect(d).toContainText('fixture-unattended');
  await page.reload();
  await expect(page.locator('.command-notice').filter({ hasText: 'Mushegh applied: open' })).toHaveCount(0);
});

test('shows a truthful loader while the brain snapshot is pending', async ({ page }) => {
  await page.unroute('**/api/hud.json');
  await page.route('**/api/hud.json', async route => { await new Promise(resolve => setTimeout(resolve, 700)); await route.fulfill({ json: snapshot() }); });
  await page.reload();
  await expect(page.getByText('Connecting to Mushegh').first()).toBeVisible();
  await expect(page.getByText('Test objective')).toBeVisible();
});

for (const width of [320, 375, 768, 1024, 1440]) test(`fits viewport ${width}px`, async ({ page }) => {
  await page.setViewportSize({ width, height: 1000 });
  await expect(page.getByRole('search')).toBeVisible();
  await expect.poll(async () => page.locator('[data-visible=true]').evaluateAll(elements => elements.every(element => element.getBoundingClientRect().right <= innerWidth + 1))).toBe(true);
  const dimensions = await page.evaluate(() => ({ viewport: innerWidth, document: document.documentElement.scrollWidth, panels: [...document.querySelectorAll('[data-visible=true]')].map(element => { const rect = element.getBoundingClientRect(); return { x: rect.x, right: rect.right, width: rect.width, height: rect.height }; }) }));
  expect(dimensions.document).toBeLessThanOrEqual(width);
  for (const panel of dimensions.panels) { expect(panel.x).toBeGreaterThanOrEqual(0); expect(panel.right).toBeLessThanOrEqual(width + 1); expect(panel.width).toBeGreaterThan(100); expect(panel.height).toBeGreaterThan(100); }
  await page.screenshot({ path: `test-results/hud-${width}.png`, fullPage: true });
});

test('respects reduced motion and keyboard focus', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' }); await page.reload();
  await expect(page.getByRole('textbox', { name: 'Mushegh command or canvas search' })).toBeVisible();
  await page.keyboard.press('Control+k');
  await expect(page.getByRole('textbox', { name: 'Mushegh command or canvas search' })).toBeFocused();
  await page.keyboard.press('Escape');
  const durations = await page.locator('.tile-slot').evaluateAll(elements => elements.map(element => getComputedStyle(element).transitionDuration));
  expect(durations.every(duration => duration.split(',').every(value => parseFloat(value) === 0))).toBe(true);
});
