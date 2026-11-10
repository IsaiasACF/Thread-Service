/* Controlled outages affect only the containers created for B's local tests. */
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const { docker } = require('../final/docker.cjs');

async function main() {
  const [playwrightModule, browserReport, output, browserExecutable] = process.argv.slice(2);
  const previous = JSON.parse(fs.readFileSync(browserReport));
  assert(previous.passed, 'Complete the browser E2E first');
  const { fixtures: f, origin } = previous;
  const { chromium } = require(path.resolve(playwrightModule));
  const browser = await chromium.launch({ headless: true, ...(browserExecutable ? { executablePath: browserExecutable } : {}) });
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  await context.addInitScript(id => localStorage.setItem('thread.identity.v1', JSON.stringify({ id })), f.authorId);
  const page = await context.newPage();
  const report = { kind: 'real-docker-outage-recovery', passed: false, steps: {}, fixtures: {}, errors: [] };
  const stopped = new Set();
  const paused = new Set();
  function stop(name) { docker(['stop', name]); stopped.add(name); }
  function start(name) { docker(['start', name]); stopped.delete(name); }
  async function graphql(query, variables) {
    return page.evaluate(async args => (await fetch('/graphql', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(args),
    })).json(), { query, variables });
  }
  try {
    fs.mkdirSync(output, { recursive: true });
    stop('thread-b-base-messages-1');
    await page.goto(origin + '/polls/pendiente');
    await page.getByLabel('ID del canal', { exact: true }).fill(f.channelId);
    await page.getByLabel('Pregunta', { exact: true }).fill('Recuperación real de Messages ' + Date.now());
    await page.getByLabel('Opciones, una por línea').fill('Sí\nNo');
    await page.getByLabel('Duración en minutos').fill('15');
    const pending = page.waitForResponse(r => r.url().endsWith('/graphql') && /mutation\s+CreatePoll\b/.test(r.request().postDataJSON()?.query || ''));
    await page.getByRole('button', { name: 'Crear encuesta', exact: true }).click();
    const response = await pending;
    const request = response.request().postDataJSON();
    const body = await response.json();
    assert(!body.errors, JSON.stringify(body));
    const poll = body.data.createPoll;
    assert.equal(poll.status, 'pending_announcement');
    report.fixtures.pendingPollId = poll.pollId;
    await page.getByRole('link', { name: `Abrir encuesta ${poll.pollId}` }).click();
    await page.getByText('Pendiente de publicación', { exact: true }).waitFor();
    assert(await page.getByRole('button', { name: 'Votar', exact: true }).isDisabled());
    await page.screenshot({ path: path.join(output, '08-encuesta-pendiente-messages-caido.png'), fullPage: true });
    report.steps.pending_when_messages_down = true;

    const repeated = await graphql(request.query, request.variables);
    assert.equal(repeated.data.createPoll.pollId, poll.pollId);
    assert.equal(repeated.data.createPoll.status, 'pending_announcement');
    const conflict = await graphql(request.query, { ...request.variables, input: { ...request.variables.input, question: 'Changed body' } });
    assert.equal(conflict.errors?.[0]?.extensions?.code, 'CONFLICT');
    report.steps.idempotency_reuses_poll_and_rejects_changed_body = true;

    start('thread-b-base-messages-1');
    await page.getByText('Abierta', { exact: true }).waitFor({ timeout: 90000 });
    await page.screenshot({ path: path.join(output, '09-encuesta-recuperada.png'), fullPage: true });
    report.steps.pending_activates_after_messages_recovery = true;
    const announcement = await graphql('query RecoveryMessages($c:ID!){messages(channelId:$c){id content}}', { c: f.channelId });
    assert(announcement.data.messages.some(m => m.content.includes(poll.pollId)));
    report.steps.announcement_visible_in_same_messages_service = true;

    stop('thread-b-app-polls-api-1');
    const isolation = await graphql('query Isolation($i:ID!,$c:ID!,$m:ID!){integral(id:$i){id} messages(channelId:$c){id} replies(channelId:$c,messageId:$m){id}}',
      { i: f.integralId, c: f.channelId, m: f.messageId });
    assert(!isolation.errors, JSON.stringify(isolation));
    assert.equal(isolation.data.integral.id, f.integralId);
    assert(isolation.data.replies.some(r => r.id === f.replyId));
    const unavailable = await graphql('query Unavailable($p:ID!){poll(id:$p){pollId}}', { p: f.pollId });
    assert.equal(unavailable.errors?.[0]?.extensions?.code, 'UPSTREAM_UNAVAILABLE');
    report.steps.polls_outage_does_not_block_chat_threads_integrals = true;
    start('thread-b-app-polls-api-1');
    if (process.env.FINAL_STACK_DIR) {
      stop('integrals');
      const threads = await graphql('query ThreadsWhileIntegralsDown($c:ID!,$m:ID!){replies(channelId:$c,messageId:$m){id}}', {c:f.channelId,m:f.messageId});
      assert(!threads.errors && threads.data.replies.some(r => r.id === f.replyId));
      const unavailableIntegral = await graphql('query IntegralDown($id:ID!){integral(id:$id){id}}',{id:f.integralId});
      assert.equal(unavailableIntegral.errors?.[0]?.extensions?.code,'UPSTREAM_UNAVAILABLE');
      start('integrals');
      report.steps.integrals_outage_does_not_block_threads = true;
    }
    // Close the recovery poll so no deferred test announcement remains pending.
    let result;
    for (let i = 0; i < 30; i++) {
      result = await graphql('query Recovery($p:ID!){poll(id:$p){pollId}}', { p: poll.pollId });
      if (!result.errors) break;
      await new Promise(resolve => setTimeout(resolve, 1000));
    }
    assert(!result.errors, JSON.stringify(result));
    const closed = await graphql('mutation CloseRecovery($p:ID!,$u:ID!){closePoll(pollId:$p,authorId:$u){status}}', { p: poll.pollId, u: f.authorId });
    assert.equal(closed.data?.closePoll?.status, 'closed');
    report.steps.recovered_poll_closed = true;
    if (process.env.FINAL_STACK_DIR) {
      await page.goto(origin + '/channels/' + f.channelId);
      const root = page.getByRole('article', {name:'Mensaje '+f.messageId,exact:true});
      await root.waitFor();
      await root.getByRole('button',{name:/Ver respuestas/}).click();
      const draft = 'Resultado incierto local ' + Date.now();
      await page.getByLabel('Tu respuesta',{exact:true}).fill(draft);
      let writes = 0;
      page.on('request', req => { if(req.url().endsWith('/graphql') && /mutation\s+CreateReply\b/.test(req.postDataJSON()?.query || '')) writes++; });
      docker(['pause','chat-threads']); paused.add('chat-threads');
      const waiting = page.waitForResponse(r => r.url().endsWith('/graphql') && /mutation\s+CreateReply\b/.test(r.request().postDataJSON()?.query || ''));
      await page.getByRole('button',{name:/Publicar respuesta/}).click();
      const timedOut = await (await waiting).json();
      assert.equal(timedOut.errors?.[0]?.extensions?.code,'UPSTREAM_TIMEOUT');
      await page.getByText(/El resultado es incierto/).waitFor();
      assert.equal(await page.getByLabel('Tu respuesta',{exact:true}).inputValue(),draft);
      docker(['unpause','chat-threads']); paused.delete('chat-threads');
      const after = await graphql('query AfterUncertainWrite($c:ID!,$m:ID!){replies(channelId:$c,messageId:$m){id content}}',{c:f.channelId,m:f.messageId});
      assert(!after.errors);
      const matching = after.data.replies.filter(item=>item.content===draft);
      assert(matching.length<=1);
      await page.waitForTimeout(5500);
      assert.equal(writes,1);
      assert.equal(await page.getByLabel('Tu respuesta',{exact:true}).inputValue(),draft);
      report.steps.real_write_timeout_keeps_draft_without_automatic_retry = true;
      const finalRead = await graphql('query FinalUncertainWrite($c:ID!,$m:ID!){replies(channelId:$c,messageId:$m){id content}}',{c:f.channelId,m:f.messageId});
      assert(!finalRead.errors);
      const persisted = finalRead.data.replies.filter(item=>item.content===draft);
      assert(persisted.length<=1);
      report.uncertainWrite = {code:'UPSTREAM_TIMEOUT',postCount:writes,persistedIds:persisted.map(item=>item.id),source:'real API read 5.5 seconds after unpause'};
    }
    report.passed = true;
  } catch (error) {
    report.error = String(error.stack || error);
    process.exitCode = 1;
    await page.screenshot({ path: path.join(output, 'recovery-failure.png'), fullPage: true }).catch(() => {});
  } finally {
    for (const name of paused) { try { docker(['unpause',name]); } catch { report.passed=false; process.exitCode=1; } }
    for (const name of stopped) {
      try { start(name); } catch (error) { report.errors.push('Failed to restore ' + name); process.exitCode = 1; report.passed = false; }
    }
    report.finishedAt = new Date().toISOString();
    fs.writeFileSync(path.join(output, 'recovery-report.json'), JSON.stringify(report, null, 2));
    console.log(JSON.stringify(report, null, 2));
    await browser.close();
  }
}
main().catch(error => { console.error(error); process.exitCode = 1; });
