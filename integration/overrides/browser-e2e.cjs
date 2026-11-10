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
    startedAt: new Date().toISOString(), origin, steps: {}, fixtures: {}, requests: [], pageErrors: [], consoleErrors: [], expectedErrors: [], mode: process.env.FINAL_STACK_DIR ? "verified-final-stack" : "legacy-B-stack" };
  const browser = await chromium.launch({ headless: true, ...(browserExecutable ? { executablePath: browserExecutable } : {}) });
  const contexts = [];
  async function context() {
    const ctx = await browser.newContext({ viewport: { width: 1440, height: 1050 }, locale: 'es-CL', ...(process.env.E2E_VIDEO_DIR ? { recordVideo: { dir: process.env.E2E_VIDEO_DIR, size: { width: 1280, height: 720 } } } : {}) });
    contexts.push(ctx);
    ctx.on('page', page => {
      page.on('console', message => { if (message.type() === 'error') report.consoleErrors.push(message.text()); });
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
    const icon = await author.request.get(origin + '/favicon.svg');
    assert.equal(icon.status(), 200);
    assert(icon.headers()['content-type'].includes('image/svg+xml'));
    report.steps.favicon_resource_no_console_404 = true;
    await author.getByLabel('Tu nombre').fill(`B autor ${tag}`);
    const created = await mutation(author, 'CreateUser', () => author.getByRole('button', { name: 'Crear identidad', exact: true }).click());
    report.fixtures.authorId = created.createUser.id;
    await author.getByText(`Hola, B autor ${tag}`, { exact: true }).waitFor();
    const voterContext = await context();
    const voter = await voterContext.newPage();
    await voter.goto(origin);
    await voter.getByLabel('Tu nombre').fill(`B votante ${tag}`);
    const voterResult = await mutation(voter, 'CreateUser', () => voter.getByRole('button', { name: 'Crear identidad', exact: true }).click());
    report.fixtures.voterId = voterResult.createUser.id;
    await voter.getByText(`Hola, B votante ${tag}`, { exact: true }).waitFor();
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
    await author.getByLabel('Canal para la encuesta', { exact: true }).selectOption(report.fixtures.channelId);
    await author.getByLabel('Pregunta', { exact: true }).fill(`Encuesta real B ${tag}`);
    await author.getByLabel('Opciones, una por línea', { exact: true }).fill('Primera\nSegunda');
    await author.getByLabel('Duración en minutos').fill('15');
    const createdPoll = await mutation(author, 'CreatePoll', () => author.getByRole('button', { name: 'Crear encuesta', exact: true }).click());
    report.fixtures.pollId = createdPoll.createPoll.pollId;
    assert(['open', 'pending_announcement'].includes(createdPoll.createPoll.status));
    await author.getByRole('link', { name: `Abrir encuesta ${report.fixtures.pollId}`, exact: true }).click();
    await author.getByText('Abierta', { exact: true }).waitFor({ timeout: 45000 });
    report.steps.poll_create_and_open = true;
    const announced = await graphql(author, 'query Announcement($c:ID!){messages(channelId:$c){id channelId content}}', {c:report.fixtures.channelId});
    const announcements = announced.data.messages.filter(item => item.content.includes(report.fixtures.pollId));
    assert.equal(announcements.length, 1);
    report.fixtures.announcementId = announcements[0].id;
    report.steps.poll_announcement_once_in_shared_messages = true;

    await screenshot(author, '04-encuesta-abierta');

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

    if (process.env.FINAL_STACK_DIR) {
      await author.goto(origin + '/');
      await author.getByRole('button', { name: 'Cerrar identidad local', exact: true }).click();
      assert.equal(await author.evaluate(() => localStorage.getItem('thread.identity.v1')), null);
      await author.getByLabel('ID de usuario', { exact: true }).fill(report.fixtures.voterId);
      await author.getByRole('button', { name: 'Usar este ID', exact: true }).click();
      await author.getByText(`Hola, B votante ${tag}`, {exact:true}).waitFor();
      await author.getByLabel('ID de usuario', { exact: true }).fill(report.fixtures.authorId);
      await author.getByRole('button', { name: 'Usar este ID', exact: true }).click();
      await author.getByText(`Hola, B autor ${tag}`, {exact:true}).waitFor();
      await author.reload();
      await author.getByText(`Hola, B autor ${tag}`, {exact:true}).waitFor();
      report.steps.close_change_recover_identity_and_reload = true;
      // Create only the extra real history rows needed to cross the UI's page boundary.
      const count = await graphql(author, 'query HistoryCount{integrals(limit:1){total}}', {});
      report.historyPreparation = [];
      for (let i = count.data.integrals.total; i < 21; i++) {
        const result = await graphql(author, 'mutation PrepareHistory($latex:String!){calculateIntegral(latex:$latex){id status}}', {latex:`pagination-${tag}-${i}`});
        assert(!result.errors && result.data.calculateIntegral.status === 'failed');
        report.historyPreparation.push(result.data.calculateIntegral.id);
      }
      await author.goto(origin + '/integrals');
      await author.getByText(/Página 1/).waitFor();
      const next = author.waitForResponse(r => r.url().endsWith('/graphql') && r.request().postDataJSON()?.variables?.offset === 20);
      await author.getByRole('button', {name:'Siguiente',exact:true}).click();
      const second = await (await next).json();
      assert(!second.errors && second.data.integrals.offset === 20 && second.data.integrals.items.length > 0);
      await author.getByText(/Página 2/).waitFor();
      await author.getByRole('button', {name:'Anterior',exact:true}).click();
      await author.getByText(/Página 1/).waitFor();
      report.steps.real_history_pagination = true;
      await author.getByRole('link', {name:'Chat',exact:true}).click();
      await author.locator(`a[href='/channels/${report.fixtures.channelId}']`).click();
      const messageRow = author.getByRole('article', {name:'Mensaje '+report.fixtures.messageId,exact:true});
      await messageRow.waitFor();
      await author.getByRole('button', {name:/Actualizar mensajes/}).first().click();
      assert.equal(await messageRow.count(), 1);
      await messageRow.getByRole('button', {name:/Ver respuestas/}).click();
      await author.getByRole('article', {name:'Mensaje '+report.fixtures.replyId,exact:true}).waitFor();
      await author.getByRole('button', {name:'Cerrar respuestas',exact:true}).click();
      assert.equal(await author.getByRole('dialog', {name:'Respuestas del mensaje'}).count(), 0);
      await author.reload();
      await messageRow.waitFor();
      await messageRow.getByRole('button', {name:/Ver respuestas/}).click();
      await author.getByRole('article', {name:'Mensaje '+report.fixtures.replyId,exact:true}).waitFor();
      const check = await graphql(author, 'query Relations($u:ID!,$c:ID!,$m:ID!){user(id:$u){id} channel(id:$c){id} messages(channelId:$c){id channelId authorId content createdAt} replies(channelId:$c,messageId:$m){id channelId messageId authorId content createdAt}}', {u:report.fixtures.authorId,c:report.fixtures.channelId,m:report.fixtures.messageId});
      assert(!check.errors);
      const root = check.data.messages.find(item => item.id === report.fixtures.messageId);
      const response = check.data.replies.find(item => item.id === report.fixtures.replyId);
      for (const item of [root,response]) { assert(item && item.channelId === report.fixtures.channelId && item.authorId === report.fixtures.authorId); assert(!Number.isNaN(Date.parse(item.createdAt))); }
      assert.equal(response.messageId, root.id);
      report.readBack = check.data;
      report.steps.return_to_chat_threads_and_reload_with_relations = true;
      await screenshot(author, '10-chat-threads-after-all-tools');
      const counts = Object.fromEntries(['CreateUser','CreateChannel','SendMessage','CreateReply','CalculateIntegral','CreatePoll','VotePoll','ClosePoll'].map(operation => [operation,report.requests.filter(r => r.operation === operation).length]));
      assert.deepEqual(counts,{CreateUser:2,CreateChannel:1,SendMessage:1,CreateReply:1,CalculateIntegral:2,CreatePoll:1,VotePoll:1,ClosePoll:1});
      report.mutationCounts = counts;
      report.steps.no_automatic_duplicate_writes = true;
      await author.getByRole('button', {name:'Cerrar respuestas',exact:true}).click();
      await author.goto(origin + '/polls/' + report.fixtures.pollId);
      await author.getByText('Cerrada', {exact:true}).waitFor();
    }
    await author.setViewportSize({ width: 390, height: 844 });
    await screenshot(author, '07-encuesta-movil');
    assert(await author.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth));
    report.steps.mobile_no_horizontal_overflow = true;
    assert(report.requests.length > 0);
    assert(report.requests.every(req => req.origin === origin && req.path === '/graphql'));
    assert.equal(report.pageErrors.length, 0, JSON.stringify(report.pageErrors));
    assert.equal(report.consoleErrors.length, 0, JSON.stringify(report.consoleErrors));
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
    for (const ctx of contexts) await ctx.close();
    await browser.close();
  }
}
main().catch(error => { console.error(error); process.exitCode = 1; });
