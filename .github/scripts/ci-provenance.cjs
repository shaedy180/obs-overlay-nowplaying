'use strict';

// Artifact metadata is a receipt, never executable input. A green PR is reusable
// only for the identical merge tree and parents, in this exact workflow.
const { writeFileSync } = require('node:fs');
const { execFileSync } = require('node:child_process');
const assert = require('node:assert/strict');

function requireChecks(results, required) {
  assert.ok(required.length > 0, 'No required validation jobs configured');
  for (const id of required) {
    assert.equal(results[id]?.result, 'success', `Required job ${id} did not pass`);
  }
  for (const [id, job] of Object.entries(results)) {
    assert.ok(['success', 'skipped'].includes(job.result), `Job ${id} failed or was cancelled`);
  }
}

function requireSameMerge(tested, merged, head) {
  assert.equal(merged.parents.length, 2, 'A reviewed merge commit is required');
  assert.equal(merged.parents[1].sha, head, 'Merged PR head does not match');
  assert.equal(tested.tree.sha, merged.tree.sha, 'PR tested a different source tree');
  assert.deepEqual(tested.parents.map(p => p.sha), merged.parents.map(p => p.sha),
    'PR tested different merge parents; update the PR and rerun its checks');
}

function selectRun(runs, workflowId, path, pr) {
  const matching = runs.filter(run => run.workflow_id === workflowId && run.path === path &&
    run.event === 'pull_request' && run.head_sha === pr.head.sha &&
    run.head_repository?.id === pr.head.repo.id &&
    // GitHub can clear this association after merge. The receipt's PR number,
    // tested commit parents and merged PR head provide the durable binding.
    (!run.pull_requests.length || run.pull_requests.some(item => item.number === pr.number)));
  matching.sort((a, b) => b.id - a.id);
  assert.ok(matching.length, 'No matching PR workflow run exists');
  const run = matching[0];
  assert.equal(run.status, 'completed', 'Latest PR run has not completed');
  assert.equal(run.conclusion, 'success', 'Latest PR run did not pass');
  return run;
}

async function verifyMerge({ github, context, core }) {
  const repo = context.repo;
  const { data: merged } = await github.rest.git.getCommit({ ...repo, commit_sha: context.sha });
  const prs = await github.paginate(github.rest.repos.listPullRequestsAssociatedWithCommit,
    { ...repo, commit_sha: context.sha, per_page: 100 });
  const matching = prs.filter(pr => pr.merged_at && pr.base.ref === 'main' &&
    pr.base.repo.full_name === `${repo.owner}/${repo.repo}` && pr.merge_commit_sha === context.sha);
  assert.equal(matching.length, 1, 'Exactly one merged PR must own this main commit');
  const pr = matching[0];
  const { data: current } = await github.rest.actions.getWorkflowRun({ ...repo, run_id: context.runId });
  const { data: listed } = await github.rest.actions.listWorkflowRuns({ ...repo,
    workflow_id: current.workflow_id, event: 'pull_request', head_sha: pr.head.sha, per_page: 100 });
  const run = selectRun(listed.workflow_runs, current.workflow_id, current.path, pr);
  const artifacts = await github.paginate(github.rest.actions.listWorkflowRunArtifacts,
    { ...repo, run_id: run.id, per_page: 100 });
  const pattern = new RegExp(`^validated-pr-${pr.number}-([0-9a-f]{40})-attempt-${run.run_attempt}$`);
  const receipts = artifacts.filter(a => !a.expired && pattern.test(a.name));
  assert.equal(receipts.length, 1, 'PR validation receipt is missing, expired or ambiguous');
  const testedSha = receipts[0].name.match(pattern)[1];
  const { data: tested } = await github.rest.git.getCommit({ ...repo, commit_sha: testedSha });
  requireSameMerge(tested, merged, pr.head.sha);
  core.notice(`Reused successful PR #${pr.number} checks: ${run.html_url}; identical tree ${merged.tree.sha}`);
  await core.summary.addHeading('Verified PR checks').addRaw(
    `PR #${pr.number}: ${run.html_url}\n\nIdentical source tree: \`${merged.tree.sha}\`. ` +
    'No test suite was repeated on main.\n').write();
}

async function recordChecks({ github, context, core }) {
  requireChecks(JSON.parse(process.env.CI_JOB_RESULTS), JSON.parse(process.env.CI_REQUIRED_JOBS));
  if (context.eventName !== 'pull_request') return;
  const { data: tested } = await github.rest.git.getCommit({ ...context.repo, commit_sha: context.sha });
  const checkedOut = execFileSync('git', ['rev-parse', 'HEAD'], { encoding: 'utf8' }).trim();
  assert.equal(checkedOut, context.sha, 'Receipt must describe the checked-out PR merge');
  assert.deepEqual(tested.parents.map(p => p.sha),
    [context.payload.pull_request.base.sha, context.payload.pull_request.head.sha],
    'Unexpected PR merge parents');
  const attempt = Number(process.env.GITHUB_RUN_ATTEMPT);
  assert.ok(Number.isSafeInteger(attempt) && attempt > 0, 'Invalid run attempt');
  const receipt = { repository: context.repo, run: context.runId, attempt, merge: context.sha,
    tree: tested.tree.sha, head: context.payload.pull_request.head.sha };
  writeFileSync('ci-validation.json', JSON.stringify(receipt, null, 2) + '\n');
  core.setOutput('artifact', `validated-pr-${context.payload.pull_request.number}-${context.sha}-attempt-${attempt}`);
}

async function main(args) {
  if (args.context.eventName === 'push' && args.context.ref === 'refs/heads/main') {
    await verifyMerge(args);
  } else {
    await recordChecks(args);
  }
}

module.exports = main;
module.exports.requireChecks = requireChecks;
module.exports.requireSameMerge = requireSameMerge;
module.exports.selectRun = selectRun;
module.exports.verifyMerge = verifyMerge;
