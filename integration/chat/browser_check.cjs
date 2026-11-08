/* Real browser/API diagnostics. No route interception and no simulated responses. */
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');

async function main() {
  const [manifestPath, fixtureReportPath, outputPath, screenshotsPath, playwrightPath] = process.argv.slice(2);
  if (!playwrightPath) throw new Error('Usage: node browser_check.cjs MANIFEST GRAPHQL_REPORT OUTPUT SCREENSHOT_DIR PLAYWRIGHT_MODULE');
  const { chromium } = require(path.resolve(playwrightPath));
  const manifest = JSON.parse(fs.readFileSync(manifestPath));
  const fixtureReport = JSON.parse(fs.readFileSync(fixtureReportPath));
  assert.equal(JSON.parse(fs.readFileSync(path.join(manifest.state, 'owner.json'))).owner, 'thread-service-chat-integration-v1');
  const origin = `http://127.0.0.1:${manifest.ports.frontend}`;
  const tag = 'ui-' + Date.now();
  const report = { kind: 'real-browser-real-services-no-interception', strict_e2e_passed: false, steps: {}, fixtures: {}, apiRequests: [], consoleErrors: [], pageErrors: [] };
  fs.mkdirSync(screenshotsPath, { recursive: true });
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, locale: 'es-CL' });
  const page = await context.newPage();
  const operations = [];
  page.on('pageerror', error => report.pageErrors.push(error.message));
  page.on('console', message => { if (message.type() === 'error') report.consoleErrors.push(message.text()); });
  page.on('request', request => {
    if (['fetch', 'xhr'].includes(request.resourceType())) {
      const url = new URL(request.url());
      report.apiRequests.push({ origin: url.origin, path: url.pathname, method: request.method() });
      assert.equal(url.origin, origin);
      assert.equal(url.pathname, '/graphql');
      const body = request.postDataJSON();
      operations.push(/(?:query|mutation)\s+(\w+)/.exec(body.query)?.[1]);
    }
  });
  async function query(document, variables) {
    const response = await fetch(origin + '/graphql', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ query: document, variables }) });
    return response.json();
  }
  async function control(service, action) {
    const id = tag + '-' + service + '-' + action + '-' + Date.now();
    const temporary = path.join(manifest.state, 'browser-control.tmp');
    fs.writeFileSync(temporary, JSON.stringify({ id, service, action }));
    fs.renameSync(temporary, path.join(manifest.state, 'control.json'));
    const deadline = Date.now() + 45000;
    while (Date.now() < deadline) {
      const output = path.join(manifest.state, 'control-result.json');
      if (fs.existsSync(output) && JSON.parse(fs.readFileSync(output)).id === id) return;
      await new Promise(resolve => setTimeout(resolve, 100));
    }
    throw new Error('Local process control timeout');
  }
  let usersStopped = false;
  try {
    await page.goto(origin, { waitUntil: 'networkidle' });
    const username = 'Usuario navegador real ' + tag;
    await page.getByLabel('Tu nombre', { exact: true }).fill(username);
    await page.getByRole('button', { name: 'Crear identidad', exact: true }).click();
    await page.getByText(/No pudimos confirmar la creación/).waitFor();
    assert.equal(await page.getByLabel('Tu nombre', { exact: true }).inputValue(), username);
    assert.equal(await page.evaluate(() => localStorage.getItem('thread.identity.v1')), null);
    assert.equal(operations.filter(operation => operation === 'CreateUser').length, 1);
    report.steps.createUser = { success: false, observed: 'Uncertain creation; name retained, no identity selected, one POST only' };
    await page.screenshot({ path: path.join(screenshotsPath, '01-bloqueo-users-real.png'), fullPage: true });
    // Continue diagnostics with a real existing ID recovered by read-only inspection
    // of the private MongoDB after the probe's failed Users POST. This is not a mock.
    const uid = fixtureReport.fixtures.user_id;
    await page.getByLabel('ID de usuario', { exact: true }).fill(uid);
    await page.getByRole('button', { name: 'Usar este ID', exact: true }).click();
    await page.getByText('Hola, ' + fixtureReport.fixtures.username, { exact: true }).waitFor();
    await page.getByRole('button', { name: 'Cerrar identidad local', exact: true }).click();
    assert.equal(await page.evaluate(() => localStorage.getItem('thread.identity.v1')), null);
    await page.getByLabel('ID de usuario', { exact: true }).fill(uid);
    await page.getByRole('button', { name: 'Usar este ID', exact: true }).click();
    await page.getByText('Hola, ' + fixtureReport.fixtures.username, { exact: true }).waitFor();
    await page.reload({ waitUntil: 'networkidle' });
    await page.getByText('Hola, ' + fixtureReport.fixtures.username, { exact: true }).waitFor();
    report.steps.existingIdentity = { success: true, user_id: uid, closeSelectReloadVerified: true, diagnosticPrerequisite: 'Existing real ID from private DB inspection after failed creation' };
    const channelName = 'navegador-' + tag;
    await page.getByRole('button', { name: 'Crear canal', exact: true }).click();
    await page.getByLabel('Nombre del canal').fill(channelName);
    await page.getByRole('button', { name: 'Crear y abrir', exact: true }).click();
    await page.getByText(/El resultado es incierto/).waitFor();
    assert.equal(await page.getByLabel('Nombre del canal').inputValue(), channelName);
    await page.getByRole('button', { name: 'Actualizar canales antes de repetir', exact: true }).click();
    await page.getByRole('link', { name: channelName, exact: true }).click();
    await page.getByRole('heading', { name: channelName, exact: true }).waitFor();
    const cid = decodeURIComponent(new URL(page.url()).pathname.split('/').pop());
    report.steps.createChannel = { success: false, recoveredByRealListQuery: true, channel_id: cid };
    const content = 'Mensaje real desde React ' + tag;
    await page.getByLabel('Nuevo mensaje', { exact: true }).fill(content);
    await page.getByRole('button', { name: 'Enviar mensaje', exact: true }).click();
    await page.getByText(/El resultado es incierto/).waitFor();
    assert.equal(await page.getByLabel('Nuevo mensaje', { exact: true }).inputValue(), content);
    await page.getByText(content, { exact: true }).waitFor();
    const article = page.getByRole('article').filter({ has: page.getByText(content, { exact: true }) });
    const mid = (await article.getAttribute('aria-label')).slice('Mensaje '.length);
    report.steps.sendMessage = { success: false, recoveredByRealPolling: true, draftPreserved: true, message_id: mid };
    await article.getByRole('button', { name: /Ver respuestas/ }).click();
    const panel = page.getByRole('dialog', { name: 'Respuestas del mensaje' });
    const replyText = 'Respuesta real desde React ' + tag;
    await panel.getByLabel('Tu respuesta', { exact: true }).fill(replyText);
    await panel.getByRole('button', { name: 'Publicar respuesta', exact: true }).click();
    await panel.getByText('Respuesta publicada.', { exact: true }).waitFor();
    const replyArticle = panel.getByRole('article').filter({ has: page.getByText(replyText, { exact: true }) });
    await replyArticle.waitFor();
    const rid = (await replyArticle.getAttribute('aria-label')).slice('Mensaje '.length);
    assert.equal(await panel.getByLabel('Tu respuesta', { exact: true }).inputValue(), '');
    report.steps.createReply = { success: true, reply_id: rid };
    await page.screenshot({ path: path.join(screenshotsPath, '02-chat-error-mensaje-y-respuesta-real.png'), fullPage: true });
    const messages = (await query('query($c:ID!){messages(channelId:$c){id channelId authorId content createdAt}}', { c: cid })).data.messages;
    const replies = (await query('query($c:ID!,$m:ID!){replies(channelId:$c,messageId:$m){id channelId messageId authorId content createdAt}}', { c: cid, m: mid })).data.replies;
    assert(messages.some(message => message.id === mid && message.channelId === cid && message.authorId === uid && message.content === content));
    assert(replies.some(reply => reply.id === rid && reply.messageId === mid && reply.channelId === cid && reply.authorId === uid && reply.content === replyText));
    await page.reload({ waitUntil: 'networkidle' });
    const reloaded = page.getByRole('article', { name: 'Mensaje ' + mid, exact: true });
    await reloaded.waitFor();
    assert.equal(await page.getByLabel('Nuevo mensaje').isEnabled(), true);
    await reloaded.getByRole('button', { name: /Ver respuestas/ }).click();
    await page.getByRole('article', { name: 'Mensaje ' + rid, exact: true }).waitFor();
    report.steps.reload = { success: true, identityRevalidated: true, realMessageAndReplyReadAgain: true };
    await page.screenshot({ path: path.join(screenshotsPath, '03-recarga-y-respuesta-real.png'), fullPage: true });
    await page.getByRole('button', { name: 'Cerrar respuestas', exact: true }).click();
    await control('users', 'stop'); usersStopped = true;
    await page.reload({ waitUntil: 'networkidle' });
    await page.getByText(/No pudimos conectar con el servicio/).first().waitFor();
    assert.equal(JSON.parse(await page.evaluate(() => localStorage.getItem('thread.identity.v1'))).id, uid);
    assert.equal(await page.getByLabel('Nuevo mensaje').isDisabled(), true);
    await page.getByText(content, { exact: true }).waitFor();
    report.steps.realOutage = { success: true, storedIdentityKept: true, writingDisabled: true, conversationReadable: true };
    await page.screenshot({ path: path.join(screenshotsPath, '04-users-no-disponible-real.png'), fullPage: true });
    await control('users', 'start'); usersStopped = false;
    const deadline = Date.now() + 15000;
    while (Date.now() < deadline) {
      const result = await query('query($id:ID!){user(id:$id){id}}', { id: uid });
      if (result.data?.user?.id === uid) break;
      await new Promise(resolve => setTimeout(resolve, 200));
    }
    await page.getByRole('button', { name: 'Revalidar identidad', exact: true }).click();
    await page.waitForFunction(() => !document.querySelector('#message-content')?.disabled);
    report.steps.outageRecovery = { success: true };
    report.fixtures = { user_id: uid, channel_id: cid, message_id: mid, reply_id: rid, content, reply: replyText };
    report.operations = [...new Set(operations)];
    report.postCounts = Object.fromEntries(['CreateUser', 'CreateChannel', 'SendMessage', 'CreateReply'].map(name => [name, operations.filter(operation => operation === name).length]));
    assert(Object.values(report.postCounts).every(count => count === 1));
    assert.equal(report.consoleErrors.length, 0);
    assert.equal(report.pageErrors.length, 0);
    report.networkVerified = true;
    report.diagnosticJourneyCompleted = true;
    report.strict_e2e_passed = ['createUser', 'createChannel', 'sendMessage', 'createReply', 'reload'].every(name => report.steps[name]?.success === true);
    console.log(JSON.stringify({ strict_e2e_passed: report.strict_e2e_passed, diagnosticJourneyCompleted: true, realBackend: true, postCounts: report.postCounts, output: outputPath }));
    return report.strict_e2e_passed ? 0 : 1;
  } finally {
    if (usersStopped) await control('users', 'start');
    fs.writeFileSync(outputPath, JSON.stringify(report, null, 2) + '\n');
    await browser.close();
  }
}
main().then(code => { process.exitCode = code; }).catch(error => { console.error(error); process.exitCode = 2; });
