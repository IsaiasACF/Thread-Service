/* Controlled outages affect only the containers created for B's local tests. */
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const { execFileSync } = require('node:child_process');

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
  function stop(name) { execFileSync('docker', ['stop', name], { stdio: 'pipe', timeout: 45000 }); stopped.add(name); }
  function start(name) { execFileSync('docker', ['start', name], { stdio: 'pipe', timeout: 45000 }); stopped.delete(name); }
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
    report.passed = true;
  } catch (error) {
    report.error = String(error.stack || error);
    process.exitCode = 1;
    await page.screenshot({ path: path.join(output, 'recovery-failure.png'), fullPage: true }).catch(() => {});
  } finally {
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
