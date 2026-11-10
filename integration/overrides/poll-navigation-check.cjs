const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');

async function main() {
  const [playwrightModule, fixturesPath, output, executablePath] = process.argv.slice(2);
  const { fixtures: f } = JSON.parse(fs.readFileSync(fixturesPath, 'utf8'));
  const { chromium } = require(path.resolve(playwrightModule));
  const browser = await chromium.launch({ headless: true, executablePath });
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, colorScheme: 'light' });
  await context.addInitScript(id => localStorage.setItem('thread.identity.v1', JSON.stringify({ id })), f.authorId);
  const page = await context.newPage();
  const report = { passed: false, kind: 'real-browser-poll-discovery-and-channel-selection', steps: {}, requests: [], errors: [] };
  fs.mkdirSync(output, { recursive: true });
  page.on('pageerror', e => report.errors.push(e.message));
  page.on('request', req => {
    if (['fetch', 'xhr'].includes(req.resourceType())) report.requests.push(new URL(req.url()).pathname);
  });
  try {
    await page.goto('http://localhost:5173/channels/' + f.channelId);
    await page.locator('#message-content').waitFor();
    await page.getByRole('link', { name: 'Encuestas', exact: true }).click();
    await page.waitForURL('**/polls/pendiente?channel=*');
    const channel = page.getByLabel('Filtrar encuestas por canal', { exact: true });
    const createChannel = page.getByLabel('Canal para la encuesta', { exact: true });
    assert.equal(await channel.inputValue(), f.channelId);
    assert.equal(await createChannel.inputValue(), f.channelId);
    const menu = page.getByLabel('Encuestas disponibles', { exact: true });
    await menu.locator(`option[value='${f.pollId}']`).waitFor({ state: 'attached', timeout: 30000 });
    report.steps.context_preselects_channel_and_discovers_existing_poll = true;
    await menu.selectOption(f.pollId);
    await page.getByRole('status').filter({ hasText: /^Cerrada$/ }).waitFor();
    await page.screenshot({ path: path.join(output, '01-listado-y-detalle.png') });
    report.steps.opens_existing_poll_without_typing_id = true;
    await page.getByLabel('Estado de las encuestas').selectOption('open');
    assert.equal(await menu.locator(`option[value='${f.pollId}']`).count(), 0);
    report.steps.status_filter_excludes_closed_poll = true;
    await page.getByLabel('Estado de las encuestas').selectOption('');

    const question = 'Prueba selector de canales ' + Date.now();
    await page.getByLabel('Pregunta', { exact: true }).fill(question);
    await page.getByLabel('Opciones, una por línea').fill('Alternativa uno\nAlternativa dos');
    await page.getByLabel('Duración en minutos').fill('60');
    const creation = page.waitForResponse(r => r.url().endsWith('/graphql') && /mutation\s+CreatePoll\b/.test(r.request().postDataJSON()?.query || ''));
    await page.getByRole('button', { name: 'Crear encuesta', exact: true }).click();
    const response = await creation;
    const body = await response.json();
    assert(!body.errors, JSON.stringify(body));
    const created = body.data.createPoll;
    report.createdPollId = created.pollId;
    assert.equal(created.channelId, f.channelId);
    await menu.locator(`option[value='${created.pollId}']`).waitFor({ state: 'attached' });
    report.steps.creation_uses_channel_selector_and_updates_directory = true;
    await menu.selectOption(created.pollId);
    await page.getByRole('heading', { name: question, exact: true }).waitFor();
    await page.getByRole('status').filter({ hasText: /^Abierta$/ }).waitFor({ timeout: 30000 });
    await page.screenshot({ path: path.join(output, '02-creada-desde-selector.png') });

    const otherId = await channel.locator('option').evaluateAll(options => options.find(o => o.value && !o.selected)?.value);
    assert(otherId);
    await channel.selectOption(otherId);
    await page.getByText('Encuestas referenciadas en los mensajes de este canal y recién creadas en esta sesión.', { exact: true }).waitFor();
    assert.equal(await menu.locator(`option[value='${created.pollId}']`).count(), 0);
    await channel.selectOption(f.channelId);
    await menu.locator(`option[value='${created.pollId}']`).waitFor({ state: 'attached' });
    report.steps.channel_filter_does_not_mix_polls = true;

    await page.setViewportSize({ width: 390, height: 844 });
    await page.getByRole('button', { name: 'Modo oscuro' }).click();
    await page.screenshot({ path: path.join(output, '03-selectores-movil-oscuro.png') });
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth && document.querySelector('main').scrollWidth <= document.querySelector('main').clientWidth));
    report.steps.mobile_dark_no_overflow = true;
    await page.getByRole('button', { name: 'Cerrar encuesta', exact: true }).click();
    await page.getByRole('status').filter({ hasText: /^Cerrada$/ }).waitFor();
    assert(report.requests.every(item => item === '/graphql'));
    assert.equal(report.errors.length, 0);
    report.steps.only_gateway_requests = true;
    report.passed = true;
  } catch (error) {
    report.error = String(error.stack || error);
    await page.screenshot({ path: path.join(output, 'failure.png') }).catch(() => {});
    process.exitCode = 1;
  } finally {
    fs.writeFileSync(path.join(output, 'report.json'), JSON.stringify(report, null, 2));
    console.log(JSON.stringify(report, null, 2));
    await browser.close();
  }
}
main().catch(error => { console.error(error); process.exitCode = 1; });
