-- GH Archive / BigQuery: candidate agent-generated merged PRs  (Mining §A.1, §B)
-- ---------------------------------------------------------------------------
-- PURPOSE: the cheap, days-scale, NO-engine, NO-label population read. It yields
-- a candidate agent-PR list with size signals and repo. It is the kill-fast
-- tripwire and the prior for M.
--
-- HONESTY ABOUT GH ARCHIVE CONTENT: PullRequestEvent payloads contain
-- additions / deletions / changed_files COUNTS and the merge flag, but NOT the
-- per-file PATH LIST or per-file add/modify status. Diff-SHAPE (new-file vs
-- modify) therefore CANNOT be read from GH Archive alone — it requires a
-- follow-up GitHub `/pulls/{n}/files` enrichment on a sample (see
-- gh_enrich_files.py). This query produces the candidate set + size prior; the
-- enrichment produces the shape mix.
--
-- DETECTION (§B) is a UNION of drifting signals — VERIFY the live identifiers
-- before running; bot handles and trailers change between releases.
-- ---------------------------------------------------------------------------
SELECT
  repo.name                                            AS repo,
  actor.login                                          AS author_login,
  JSON_VALUE(payload, '$.pull_request.html_url')       AS pr_url,
  CAST(JSON_VALUE(payload, '$.pull_request.additions')    AS INT64) AS additions,
  CAST(JSON_VALUE(payload, '$.pull_request.deletions')    AS INT64) AS deletions,
  CAST(JSON_VALUE(payload, '$.pull_request.changed_files') AS INT64) AS changed_files,
  JSON_VALUE(payload, '$.pull_request.merged_at')      AS merged_at,
  -- which signal fired (for auditing the detector's precision later)
  ARRAY_TO_STRING([
    IF(REGEXP_CONTAINS(LOWER(JSON_VALUE(payload,'$.pull_request.body')),
       r'co-authored-by:\s*claude|generated with claude code|aider|devin|codex'), 'body_trailer', NULL),
    IF(LOWER(actor.login) IN (
        'devin-ai-integration[bot]','copilot-swe-agent[bot]','sweep-ai[bot]',
        'cursoragent','cody-ai[bot]','github-actions[bot]'), 'bot_login', NULL),
    IF(REGEXP_CONTAINS(LOWER(JSON_VALUE(payload,'$.pull_request.title')),
       r'\[(devin|sweep|cursor|copilot)\]'), 'title_tag', NULL)
  ], ',') AS detection_signals
FROM `githubarchive.day.20*`           -- narrow the wildcard to your window
WHERE type = 'PullRequestEvent'
  AND JSON_VALUE(payload, '$.action') = 'closed'
  AND JSON_VALUE(payload, '$.pull_request.merged') = 'true'
  AND (
        REGEXP_CONTAINS(LOWER(JSON_VALUE(payload,'$.pull_request.body')),
          r'co-authored-by:\s*claude|generated with claude code|aider|devin|codex')
     OR LOWER(actor.login) IN (
          'devin-ai-integration[bot]','copilot-swe-agent[bot]','sweep-ai[bot]',
          'cursoragent','cody-ai[bot]')
     OR REGEXP_CONTAINS(LOWER(JSON_VALUE(payload,'$.pull_request.title')),
          r'\[(devin|sweep|cursor|copilot)\]')
      )
-- SELECTION-BIAS WARNING (put on every chart derived from this):
--   public MERGED agent PRs over-represent small, safe, dependency-style changes
--   that passed human review -> a biased, optimistic-for-modify slice. Directional
--   prior + kill-fast tripwire only; NOT the enterprise mix.
