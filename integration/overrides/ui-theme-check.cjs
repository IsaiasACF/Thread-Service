/* Visual/navigation checks against the running app, with real data and no interception. */
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');

async function main() {
  const [playwrightModule, fixturesPath, output, executablePath] = process.argv.slice(2);
  const previous = JSON.parse(fs.readFileSync(fixturesPath, 'utf8'));
  assert(previous.passed);
  const { chromium } = require(path.resolve(playwrightModule));
  fs.mkdirSync(output, { recursive: true });
  const browser = await chromium.launch({ headless: true, executablePath });
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 1000 }, colorScheme: 'light' });
  await ctx.addInitScript(id => {
    localStorage.setItem('thread.identity.v1', JSON.stringify({ id }));
    // Only seed the first document; preserve subsequent explicit theme choices.
    if (!localStorage.getItem('thread.theme.v1')) localStorage.setItem('thread.theme.v1', 'light');
  }, previous.fixtures.authorId);
  const page = await ctx.newPage();
  const report = { passed: false, kind: 'real-browser-shared-shell-light-dark', screens: [], steps: {}, pageErrors: [], consoleErrors: [], requests: [] };
  page.on('console', message => { if (message.type() === 'error') report.consoleErrors.push(message.text()); });
  page.on('request', req => { if(['fetch','xhr'].includes(req.resourceType())) { const url=new URL(req.url()); report.requests.push({origin:url.origin,path:url.pathname}); } });
  page.on('pageerror', error => report.pageErrors.push(error.message));
  const origin = previous.origin;
  await ctx.grantPermissions(['clipboard-read', 'clipboard-write'], { origin });
  const sidebar = 'aside[aria-label="Canales y herramientas"]';
  async function capture(name, theme, persistent = true) {
    await page.locator('main h1').waitFor();
    await page.getByRole('button', { name: 'Modo oscuro' }).waitFor();
    await page.waitForFunction(() => ![...document.querySelectorAll('[role="status"]')].some(el => el.textContent.trim() === 'Cargando…'));
    assert.equal(await page.locator('html').getAttribute('data-theme'), theme);
    if (persistent) assert(await page.locator(sidebar).evaluate(el => el === window.__originalSidebar));
    const geometry = await page.evaluate(() => {
      const main = document.querySelector('main'), side = document.querySelector('aside[aria-label="Canales y herramientas"]');
      const m = main.getBoundingClientRect(), s = side.getBoundingClientRect();
      return { mainLeft: m.x, mainTop: m.y, sidebarWidth: s.width, mainBackground: getComputedStyle(main).backgroundColor,
        text: getComputedStyle(main).color, horizontalOverflow: main.scrollWidth > main.clientWidth + 1 || document.documentElement.scrollWidth > innerWidth };
    });
    assert.equal(geometry.horizontalOverflow, false, name + ' overflows horizontally');
    if (name.startsWith('desktop')) {
      assert.equal(geometry.mainLeft, 256);
      assert.equal(geometry.mainTop, 58);
    }
    await page.screenshot({ path: path.join(output, name + '.png') });
    report.screens.push({ name, theme, ...geometry });
  }
  try {
    await page.goto(origin + '/channels/' + previous.fixtures.channelId);
    await page.locator('#message-content').waitFor();
    const channelLink = page.locator(`a[href='/channels/${previous.fixtures.channelId}']`);
    const channelName = await channelLink.innerText();
    await page.getByRole('searchbox', { name: 'Buscar canales' }).fill(channelName);
    assert.equal(await page.getByRole('navigation', { name: 'Canales disponibles' }).getByRole('link').count(), 1);
    await page.getByRole('searchbox', { name: 'Buscar canales' }).clear();
    report.steps.search_filters_real_channels = true;
    await page.locator(sidebar).evaluate(el => { window.__originalSidebar = el; });
    await capture('desktop-light-chat', 'light');
    const themeButton = page.getByRole('button', {name:'Modo oscuro'});
    await themeButton.focus();
    await page.keyboard.press('Space');
    assert.equal(await page.locator('html').getAttribute('data-theme'),'dark');
    await page.keyboard.press('Space');
    assert.equal(await page.locator('html').getAttribute('data-theme'),'light');
    report.steps.theme_control_operable_with_keyboard = true;
    await page.getByRole('link', { name: 'Integrales', exact: true }).click();
    await page.waitForURL('**/integrals');
    await page.getByRole('heading', { name: 'Historial', exact: true }).waitFor();
    await page.getByRole('button', { name: 'Integral definida', exact: true }).click();
    assert.equal(await page.getByLabel('Integral en LaTeX', { exact: true }).inputValue(), '\\int_0^1 x^2 \\, dx');
    report.steps.integral_example_fills_editable_field = true;
    if (process.env.FINAL_STACK_DIR) {
      await page.getByRole('button', {name:'Integral indefinida',exact:true}).click();
      const pending = page.waitForResponse(r => r.url().endsWith('/graphql') && /mutation\s+CalculateIntegral\b/.test(r.request().postDataJSON()?.query || ''));
      await page.getByRole('button',{name:'Calcular integral',exact:true}).click();
      const body = await (await pending).json();
      assert(!body.errors && body.data.calculateIntegral.status==='calculated');
      assert.equal(body.data.calculateIntegral.result.indefinite,true);
      await page.getByRole('article',{name:'Resultado de integral'}).waitFor();
      assert((await page.getByLabel('Resultado en LaTeX',{exact:true}).innerText()).endsWith('+ C'));
      report.indefiniteIntegral = body.data.calculateIntegral;
      report.steps.real_indefinite_integral_shows_constant = true;
    }
    await capture('desktop-light-integrals', 'light');
    await page.getByRole('link', { name: 'Encuestas', exact: true }).click();
    await page.waitForURL('**/polls/pendiente');
    await capture('desktop-light-polls', 'light');
    await page.getByRole('button', { name: 'Modo oscuro' }).click();
    await capture('desktop-dark-polls', 'dark');
    await page.getByLabel('ID de encuesta', { exact: true }).fill(previous.fixtures.pollId);
    await page.getByRole('button', { name: 'Abrir encuesta', exact: true }).click();
    await page.getByText('Cerrada', { exact: true }).waitFor();
    await capture('desktop-dark-poll-detail', 'dark');
    await page.getByRole('button', { name: 'Copiar enlace de encuesta' }).focus();
    await page.keyboard.press('Enter');
    await page.getByText('Copiado al portapapeles.', { exact: true }).waitFor();
    assert.equal(await page.evaluate(() => navigator.clipboard.readText()), origin + '/polls/' + previous.fixtures.pollId);
    report.steps.copy_link_uses_real_clipboard = true;
    await page.getByRole('link', { name: 'Integrales', exact: true }).click();
    await page.waitForURL('**/integrals');
    await capture('desktop-dark-integrals', 'dark');
    await page.getByRole('link', { name: 'Identidad', exact: true }).click();
    await page.waitForURL(origin + '/');
    await capture('desktop-dark-identity', 'dark');
    await page.getByRole('link', { name: 'Chat', exact: true }).click();
    await page.locator(`a[href='/channels/${previous.fixtures.channelId}']`).click();
    await page.locator('#message-content').waitFor();
    await capture('desktop-dark-chat', 'dark');
    await page.reload();
    await page.locator('#message-content').waitFor();
    await capture('desktop-dark-after-reload', 'dark', false);
    report.steps.persistent_shell_same_geometry_all_sections = true;
    report.steps.explicit_theme_persists_navigation_and_reload = true;

    await page.setViewportSize({ width: 390, height: 844 });
    await capture('mobile-dark-chat', 'dark', false);
    const rootMessage = page.getByRole('article', {name:'Mensaje '+previous.fixtures.messageId,exact:true});
    const opener = rootMessage.getByRole('button', {name:/Ver respuestas/});
    await opener.click();
    await page.getByRole('article', {name:'Mensaje '+previous.fixtures.replyId,exact:true}).waitFor();
    await capture('mobile-dark-thread', 'dark', false);
    await page.keyboard.press('Escape');
    assert.equal(await page.getByRole('dialog', {name:'Respuestas del mensaje'}).count(),0);
    assert(await opener.evaluate(el=>el===document.activeElement));
    report.steps.mobile_thread_keyboard_close_and_focus_return = true;
    await page.getByRole('button', { name: 'Canales y navegación' }).click();
    await page.getByRole('link', { name: 'Integrales', exact: true }).click();
    await page.waitForURL('**/integrals');
    await page.waitForFunction(() => document.querySelector('[aria-controls="workspace-navigation"]').getAttribute('aria-expanded') === 'false');
    assert.equal(await page.getByRole('button', { name: 'Canales y navegación' }).getAttribute('aria-expanded'), 'false');
    await capture('mobile-dark-integrals', 'dark', false);
    await page.getByRole('button', { name: 'Modo oscuro' }).click();
    await capture('mobile-light-integrals', 'light', false);
    report.steps.mobile_navigation_closes_after_selection = true;
    report.steps.mobile_theme_always_accessible = true;

    const system = await browser.newContext({ colorScheme: 'dark', reducedMotion: 'reduce' });
    const systemPage = await system.newPage();
    await systemPage.goto(origin + '/channels');
    await systemPage.getByRole('button', { name: 'Modo oscuro' }).waitFor();
    assert.equal(await systemPage.locator('html').getAttribute('data-theme'), 'dark');
    await systemPage.getByRole('button', { name: 'Modo oscuro' }).click();
    await systemPage.reload();
    await systemPage.getByRole('button', { name: 'Modo oscuro' }).waitFor();
    assert.equal(await systemPage.locator('html').getAttribute('data-theme'), 'light');
    assert.equal(await systemPage.getByRole('button', { name: 'Modo oscuro' }).evaluate(el => getComputedStyle(el).transitionDuration), '0s');
    report.steps.respects_reduced_motion = true;
    report.steps.system_theme_used_until_explicit_override = true;
    await system.close();
    assert.equal(report.pageErrors.length, 0);
    assert.equal(report.consoleErrors.length, 0, JSON.stringify(report.consoleErrors));
    assert(report.requests.every(req => req.origin===origin && req.path==='/graphql'));
    report.steps.browser_data_only_graphql = true;
    report.passed = true;
  } catch (error) {
    report.error = String(error.stack || error);
    await page.screenshot({ path: path.join(output, 'failure.png') }).catch(() => {});
    process.exitCode = 1;
  } finally {
    report.finishedAt = new Date().toISOString();
    fs.writeFileSync(path.join(output, 'report.json'), JSON.stringify(report, null, 2));
    console.log(JSON.stringify({ passed: report.passed, steps: report.steps, screens: report.screens.length, error: report.error }, null, 2));
    await browser.close();
  }
}
main().catch(error => { console.error(error); process.exitCode = 1; });
