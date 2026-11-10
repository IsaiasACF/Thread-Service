const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const { execFileSync } = require('node:child_process');

async function main() {
  const [browserReport, output] = process.argv.slice(2);
  const previous = JSON.parse(fs.readFileSync(browserReport));
  assert(previous.passed);
  const f = previous.fixtures;
  const query = `query Persistence($i:ID!,$failed:ID!,$p:ID!,$c:ID!,$m:ID!) {
    integral(id:$i){ id status result { latex numeric } }
    failed:integral(id:$failed){ id status error { code } }
    poll(id:$p){ pollId status totalVotes options { optionId voteCount } }
    replies(channelId:$c,messageId:$m){ id content }
  }`;
  const variables = { i: f.integralId, failed: f.failedIntegralId, p: f.pollId, c: f.channelId, m: f.messageId };
  const report = { kind: 'real-docker-database-restart-api-verification', passed: false, restarted: [], before: null, after: null };
  const apis = ['thread-b-app-integrals-1', 'thread-b-app-polls-api-1'];
  const databases = ['thread-b-app-integrals-mongodb-1', 'thread-b-app-polls-postgres-1'];
  function docker(args) { return execFileSync('docker', args, { encoding: 'utf8', timeout: 45000 }).trim(); }
  async function snapshot() {
    const response = await fetch(previous.origin + '/graphql', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ query, variables }), signal: AbortSignal.timeout(15000) });
    const body = await response.json();
    assert(!body.errors, JSON.stringify(body));
    assert.equal(body.data.integral.id, f.integralId);
    assert.equal(body.data.failed.status, 'failed');
    assert.equal(body.data.poll.status, 'closed');
    assert.equal(body.data.poll.totalVotes, 1);
    assert(body.data.replies.some(r => r.id === f.replyId));
    return body.data;
  }
  try {
    report.before = await snapshot();
    const started = Object.fromEntries(databases.map(name => [name, docker(['inspect', '--format', '{{.State.StartedAt}}', name])]));
    docker(['stop', ...apis]);
    docker(['restart', ...databases]);
    for (const name of databases) {
      for (let i = 0; i < 60; i++) {
        if (docker(['inspect', '--format', '{{.State.Health.Status}}', name]) === 'healthy') break;
        await new Promise(resolve => setTimeout(resolve, 500));
      }
      assert.equal(docker(['inspect', '--format', '{{.State.Health.Status}}', name]), 'healthy');
      const after = docker(['inspect', '--format', '{{.State.StartedAt}}', name]);
      assert.notEqual(after, started[name]);
      report.restarted.push({ name, before: started[name], after });
    }
    docker(['start', ...apis]);
    let last;
    for (let i = 0; i < 40; i++) {
      try { report.after = await snapshot(); last = null; break; }
      catch (error) { last = error; await new Promise(resolve => setTimeout(resolve, 500)); }
    }
    if (last) throw last;
    assert.deepEqual(report.after, report.before);
    report.passed = true;
  } catch (error) { report.error = String(error.stack || error); process.exitCode = 1; }
  finally {
    docker(['start', ...apis]);
    report.finishedAt = new Date().toISOString();
    fs.mkdirSync(output, { recursive: true });
    fs.writeFileSync(path.join(output, 'persistence-report.json'), JSON.stringify(report, null, 2));
    console.log(JSON.stringify({ passed: report.passed, restarted: report.restarted, error: report.error }, null, 2));
  }
}
main().catch(error => { console.error(error); process.exitCode = 1; });
