/* Real Chromium -> Vite -> GraphQL Gateway -> real REST services. No interception. */
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');

async function main() {
  const [playwrightModule, output, browserExecutable] = process.argv.slice(2);
  assert(playwrightModule && output, 'Usage: node browser-e2e.cjs PLAYWRIGHT_MODULE OUTPUT_DIR [CHROMIUM]');
  const { chromium } = require(path.resolve(playwrightModule));
  const origin = process.env.B_E2E_ORIGIN || 'http://localhost:5173';
  fs.mkdirSync(output, { recursive: true });
  const report = { kind: 'real-browser-real-docker-services-no-mocks', passed: false,
    startedAt: new Date().toISOString(), origin, steps: {}, fixtures: {}, requests: [], pageErrors: [], expectedErrors: [] };
  const browser = await chromium.launch({ headless: true, ...(browserExecutable ? { executablePath: browserExecutable } : {}) });
  const contexts = [];
  async function context() {
    const ctx = await browser.newContext({ viewport: { width: 1440, height: 1050 }, locale: 'es-CL' });
    contexts.push(ctx);
    ctx.on('page', page => {
      page.on('pageerror', error => report.pageErrors.push(error.message));
      page.on('request', req => {
        if (req.resourceType() !== 'fetch' && req.resourceType() !== 'xhr') return;
        const url = new URL(req.url());
        let operation;
        try { operation = /(?:query|mutation)\s+(\w+)/.exec(req.postDataJSON()?.query || '')?.[1] || 'anonymous'; } catch { operation = 'unknown'; }
        report.requests.push({ method: req.method(), origin: url.origin, path: url.pathname, operation });
      });
    });
    return ctx;
  }
  async function mutation(page, operation, action) {
    const pending = page.waitForResponse(response => {
      if (new URL(response.url()).pathname !== '/graphql') return false;
      try { return new RegExp(`mutation\\s+${operation}\\b`).test(response.request().postDataJSON().query); } catch { return false; }
    }, { timeout: 45000 });
    await action();
    const response = await pending;
    const body = await response.json();
    assert.equal(response.status(), 200);
    assert(!body.errors, JSON.stringify(body));
    return body.data;
  }
  async function graphql(page, query, variables) {
    return page.evaluate(async ({ query, variables }) => {
      const response = await fetch('/graphql', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ query, variables }) });
      return response.json();
    }, { query, variables });
  }
  async function screenshot(page, name) {
    await page.screenshot({ path: path.join(output, name + '.png'), fullPage: true });
  }
  const tag = Date.now();
  let author;
  try {
    const authorContext = await context();
    author = await authorContext.newPage();
    await author.goto(origin);
    await author.getByLabel('Tu nombre').fill(`B autor ${tag}`);
    const created = await mutation(author, 'CreateUser', () => author.getByRole('button', { name: 'Crear identidad', exact: true }).click());
    report.fixtures.authorId = created.createUser.id;
    await author.getByText(`Hola, B autor ${tag}`, { exact: true }).waitFor();
    await author.getByRole('button', { name: 'Crear canal', exact: true }).click();
    await author.getByLabel('Nombre del canal').fill(`B integración ${tag}`);
    const channel = await mutation(author, 'CreateChannel', () => author.getByRole('button', { name: 'Crear y abrir' }).click());
    report.fixtures.channelId = channel.createChannel.id;
    await author.locator('#message-content').fill(`Mensaje real B ${tag}`);
    const message = await mutation(author, 'SendMessage', () => author.getByRole('button', { name: /Enviar mensaje/ }).click());
    report.fixtures.messageId = message.sendMessage.id;
    report.steps.identity_channel_message = true;

    await author.getByRole('button', { name: /Ver respuestas/ }).first().click();
    await author.getByLabel('Tu respuesta', { exact: true }).fill(`Respuesta real B ${tag}`);
    const reply = await mutation(author, 'CreateReply', () => author.getByRole('button', { name: /Publicar respuesta/ }).click());
    report.fixtures.replyId = reply.createReply.id;
    await author.getByText(`Respuesta real B ${tag}`, { exact: true }).waitFor();
    report.steps.threads = true;
    await screenshot(author, '01-chat-threads');

    await author.goto(origin + '/integrals');
    await author.getByLabel('Integral en LaTeX', { exact: true }).fill('\\int_0^1 x^2 \\, dx');
    const success = await mutation(author, 'CalculateIntegral', () => author.getByRole('button', { name: 'Calcular integral', exact: true }).click());
    assert.equal(success.calculateIntegral.status, 'calculated');
    assert(Math.abs(success.calculateIntegral.result.numeric - 1/3) < 1e-9);
    report.fixtures.integralId = success.calculateIntegral.id;
    await author.getByRole('link', { name: 'Abrir detalle del cálculo' }).waitFor();
    await screenshot(author, '02-integral-calculada');
    await author.getByRole('link', { name: 'Abrir detalle del cálculo' }).click();
    await author.getByRole('article', { name: 'Resultado de integral' }).waitFor();
    await author.reload();
    await author.getByRole('article', { name: 'Resultado de integral' }).waitFor();
    report.steps.integral_success_detail_reload = true;

    await author.goto(origin + '/integrals');
    await author.getByLabel('Integral en LaTeX', { exact: true }).fill('x + 1');
    const failed = await mutation(author, 'CalculateIntegral', () => author.getByRole('button', { name: 'Calcular integral', exact: true }).click());
    assert.equal(failed.calculateIntegral.status, 'failed');
    assert.equal(failed.calculateIntegral.error.code, 'NOT_AN_INTEGRAL');
    report.fixtures.failedIntegralId = failed.calculateIntegral.id;
    await author.getByText('No se pudo resolver', { exact: true }).waitFor();
    await author.getByRole('combobox').selectOption('failed');
    await author.getByRole('link', { name: 'x + 1', exact: true }).first().waitFor();
    report.steps.integral_failed_history_filter = true;
    await screenshot(author, '03-integral-fallida-historial');

    await author.goto(origin + '/polls/pendiente');
    await author.getByLabel('ID del canal', { exact: true }).fill(report.fixtures.channelId);
    await author.getByLabel('Pregunta', { exact: true }).fill(`Encuesta real B ${tag}`);
    await author.getByLabel('Opciones, una por línea', { exact: true }).fill('Primera\nSegunda');
    await author.getByLabel('Duración en minutos').fill('15');
    const createdPoll = await mutation(author, 'CreatePoll', () => author.getByRole('button', { name: 'Crear encuesta', exact: true }).click());
    report.fixtures.pollId = createdPoll.createPoll.pollId;
    assert(['open', 'pending_announcement'].includes(createdPoll.createPoll.status));
    await author.getByRole('link', { name: `Abrir encuesta ${report.fixtures.pollId}`, exact: true }).click();
    await author.getByText('Abierta', { exact: true }).waitFor({ timeout: 45000 });
    report.steps.poll_create_and_open = true;
    await screenshot(author, '04-encuesta-abierta');

    const voterContext = await context();
    const voter = await voterContext.newPage();
    await voter.goto(origin);
    await voter.getByLabel('Tu nombre').fill(`B votante ${tag}`);
    const voterResult = await mutation(voter, 'CreateUser', () => voter.getByRole('button', { name: 'Crear identidad', exact: true }).click());
    report.fixtures.voterId = voterResult.createUser.id;
    await voter.getByText(`Hola, B votante ${tag}`, { exact: true }).waitFor();
    await voter.goto(origin + '/polls/' + report.fixtures.pollId);
    await voter.getByRole('radio', { name: /Segunda/ }).check();
    const cast = await mutation(voter, 'VotePoll', () => voter.getByRole('button', { name: 'Votar', exact: true }).click());
    assert.equal(cast.votePoll.voterId, report.fixtures.voterId);
    report.fixtures.optionId = cast.votePoll.optionId;
    await voter.getByText('Voto registrado.', { exact: true }).waitFor();
    await voter.getByText(/1 votos/).first().waitFor();
    report.steps.second_identity_vote_results = true;
    await screenshot(voter, '05-voto-resultados');

    const duplicate = await graphql(voter, 'mutation Duplicate($p:ID!,$u:ID!,$o:ID!){votePoll(pollId:$p,voterId:$u,optionId:$o){pollId}}',
      { p: report.fixtures.pollId, u: report.fixtures.voterId, o: report.fixtures.optionId });
    assert.equal(duplicate.errors?.[0]?.extensions?.code, 'CONFLICT');
    const forbidden = await graphql(voter, 'mutation Forbidden($p:ID!,$u:ID!){closePoll(pollId:$p,authorId:$u){pollId}}',
      { p: report.fixtures.pollId, u: report.fixtures.voterId });
    assert.equal(forbidden.errors?.[0]?.extensions?.code, 'FORBIDDEN');
    report.expectedErrors.push({ scenario: 'duplicate_vote', code: 'CONFLICT' }, { scenario: 'foreign_close', code: 'FORBIDDEN' });
    assert.equal(await voter.getByRole('button', { name: 'Cerrar encuesta', exact: true }).count(), 0);
    report.steps.duplicate_vote_foreign_close_rejected = true;

    await mutation(author, 'ClosePoll', () => author.getByRole('button', { name: 'Cerrar encuesta', exact: true }).click());
    await author.getByText('Cerrada', { exact: true }).waitFor();
    await voter.reload();
    await voter.getByText('Cerrada', { exact: true }).waitFor();
    assert(await voter.getByRole('button', { name: 'Votar', exact: true }).isDisabled());
    const closedVote = await graphql(author, 'mutation ClosedVote($p:ID!,$u:ID!,$o:ID!){votePoll(pollId:$p,voterId:$u,optionId:$o){pollId}}',
      { p: report.fixtures.pollId, u: report.fixtures.authorId, o: report.fixtures.optionId });
    assert.equal(closedVote.errors?.[0]?.extensions?.code, 'CONFLICT');
    report.expectedErrors.push({ scenario: 'closed_poll_vote', code: 'CONFLICT' });
    report.steps.author_close_persists_after_reload = true;
    await screenshot(author, '06-encuesta-cerrada');

    await author.setViewportSize({ width: 390, height: 844 });
    await screenshot(author, '07-encuesta-movil');
    assert(await author.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth));
    report.steps.mobile_no_horizontal_overflow = true;
    assert(report.requests.length > 0);
    assert(report.requests.every(req => req.origin === origin && req.path === '/graphql'));
    assert.equal(report.pageErrors.length, 0, JSON.stringify(report.pageErrors));
    report.steps.browser_data_only_graphql = true;
    report.passed = true;
  } catch (error) {
    report.error = String(error.stack || error);
    if (author && !author.isClosed()) await screenshot(author, 'failure').catch(() => {});
    process.exitCode = 1;
  } finally {
    report.finishedAt = new Date().toISOString();
    fs.writeFileSync(path.join(output, 'browser-report.json'), JSON.stringify(report, null, 2));
    console.log(JSON.stringify({ passed: report.passed, steps: report.steps, error: report.error, requests: report.requests.length }, null, 2));
    await browser.close();
  }
}
main().catch(error => { console.error(error); process.exitCode = 1; });
