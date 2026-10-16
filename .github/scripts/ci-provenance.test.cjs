'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const { requireChecks, requireSameMerge, selectRun, verifyMerge } = require('./ci-provenance.cjs');
const commit = (tree = 'tree', base = 'base', head = 'head') => ({
  tree: { sha: tree }, parents: [{ sha: base }, { sha: head }]
});
const pr = { number: 1, head: { sha: 'head', repo: { id: 2 } }, merged_at: 'now',
  base: { ref: 'main', repo: { full_name: 'owner/repo' } }, merge_commit_sha: 'merged' };
const run = { id: 10, workflow_id: 3, path: '.github/workflows/ci.yml', event: 'pull_request',
  head_sha: 'head', head_repository: { id: 2 }, pull_requests: [{ number: 1 }],
  status: 'completed', conclusion: 'success', run_attempt: 2, html_url: 'https://example.invalid/run' };
test('requires successful validation and rejects failure, cancellation and required skips', () => {
  requireChecks({ build: { result: 'success' }, release: { result: 'skipped' } }, ['build']);
  for (const result of ['failure', 'cancelled', 'skipped', undefined]) {
    assert.throws(() => requireChecks({ build: { result } }, ['build']));
  }
  assert.throws(() => requireChecks({ build: { result: 'success' }, extra: { result: 'failure' } }, ['build']));
  assert.throws(() => requireChecks({}, []));
});
test('requires identical tested tree, base, head and merge structure', () => {
  requireSameMerge(commit(), commit(), 'head');
  for (const tested of [commit('changed'), commit('tree', 'stale'), commit('tree', 'base', 'other')]) {
    assert.throws(() => requireSameMerge(tested, commit(), 'head'));
  }
  assert.throws(() => requireSameMerge(commit(), { ...commit(), parents: [{ sha: 'head' }] }, 'head'));
  assert.throws(() => requireSameMerge(commit(), commit(), 'other'));
});
test('never substitutes an older success for a failing or incomplete latest run', () => {
  assert.equal(selectRun([run], 3, run.path, pr).id, 10);
  assert.equal(selectRun([{ ...run, pull_requests: [] }], 3, run.path, pr).id, 10);
  for (const patch of [{ conclusion: 'failure' }, { status: 'in_progress' }]) {
    assert.throws(() => selectRun([run, { ...run, id: 11, ...patch }], 3, run.path, pr));
  }
});
test('rejects unrelated workflow, event, head, repository and PR', () => {
  for (const patch of [{ workflow_id: 4 }, { path: 'other.yml' }, { event: 'push' },
    { head_sha: 'old' }, { head_repository: { id: 9 } }, { pull_requests: [{ number: 99 }] }]) {
    assert.throws(() => selectRun([{ ...run, ...patch }], 3, run.path, pr));
  }
});
function harness(patch = {}) {
  const calls = [];
  const github = { rest: { git: { getCommit: async ({ commit_sha }) => ({ data:
    commit_sha === 'merged' ? commit() : (patch.tested || commit()) }) },
  repos: { listPullRequestsAssociatedWithCommit: 'prs' }, actions: {
    getWorkflowRun: async () => ({ data: run }),
    listWorkflowRuns: async () => ({ data: { workflow_runs: [patch.run || run] } }),
    listWorkflowRunArtifacts: 'artifacts' } },
  paginate: async method => method === 'prs' ? (patch.prs || [pr]) : (patch.artifacts || [{
    name: `validated-pr-1-${'a'.repeat(40)}-attempt-2`, expired: false }]) };
  const summary = { addHeading() { return this; }, addRaw() { return this; }, async write() { calls.push('success'); } };
  return { github, context: { repo: { owner: 'owner', repo: 'repo' }, sha: 'merged', runId: 20 },
    core: { notice() {}, summary }, calls };
}
test('main gate validates a matching receipt without downloading or executing artifacts', async () => {
  const args = harness(); await verifyMerge(args); assert.deepEqual(args.calls, ['success']);
});
test('main gate fails closed on absent, expired, ambiguous or stale-attempt receipts', async () => {
  const valid = { name: `validated-pr-1-${'a'.repeat(40)}-attempt-2`, expired: false };
  for (const artifacts of [[], [{ ...valid, expired: true }], [valid, valid],
    [{ ...valid, name: valid.name.replace('attempt-2', 'attempt-1') }],
    [{ ...valid, name: valid.name.replace('pr-1-', 'pr-99-') }]]) {
    await assert.rejects(verifyMerge(harness({ artifacts })));
  }
  await assert.rejects(verifyMerge(harness({ prs: [] })));
  await assert.rejects(verifyMerge(harness({ tested: commit('different') })));
});
