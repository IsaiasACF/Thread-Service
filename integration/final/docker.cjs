/* Resolve legacy B names only inside the explicitly selected owned final project. */
const path = require('node:path');
const { execFileSync } = require('node:child_process');
const assert = require('node:assert/strict');
const directory = process.env.FINAL_STACK_DIR;
const services = {'thread-b-base-messages-1':'chat-messages','thread-b-app-integrals-1':'integrals','thread-b-app-polls-api-1':'polls-api','thread-b-app-integrals-mongodb-1':'integrals-mongodb','thread-b-app-polls-postgres-1':'polls-postgres'};
function run(action, names = []) {
  assert(directory, 'FINAL_STACK_DIR is required');
  return execFileSync(process.env.FINAL_PYTHON || 'python3', [path.join(__dirname,'run.py'),'--directory',directory,action,...names], {encoding:'utf8',stdio:['ignore','pipe','pipe'],timeout:180000}).trim();
}
function service(name) { return services[name] || name; }
function docker(args) {
  if (!directory) return execFileSync('docker',args,{encoding:'utf8',timeout:90000}).trim();
  if (['stop','start','restart','pause','unpause'].includes(args[0])) return run(args[0],args.slice(1).map(service));
  assert.equal(args[0],'inspect');
  const id = run('id',[service(args.at(-1))]);
  assert(/^[a-f0-9]{12,64}$/.test(id), 'Expected exactly one owned container');
  return execFileSync('docker',[...args.slice(0,-1),id],{encoding:'utf8',timeout:45000}).trim();
}
module.exports = {docker, run};
