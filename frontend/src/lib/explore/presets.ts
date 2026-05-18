// Preset library for the Data Explorer page.
//
// Pure data + a couple of helpers. No Svelte imports here — extracting these
// keeps the page component focused on rendering and interaction state, lets
// us snapshot/test the SQL strings in isolation, and makes it easy to share
// the catalog with future consumers (saved-query panel, CLI playground, etc.).
//
// Convention: every "winner vs runner-up" preset emits the same first eight
// columns so a reader can compare results across panels without re-orienting:
//
//   ac_eci_no | constituency | winner | win_party | runner_up | ru_party
//             | margin_votes | margin_pct
//
// Some presets append extra context columns (winner_share_pct, nota_pct, …);
// the leading eight stay identical.

export interface Preset {
  /** Stable id used for selection / URL state / tests. Lowercase snake_case. */
  id: string;
  /** Short label rendered on the chip. */
  label: string;
  /** One-line tooltip / "selected query" caption explaining the question. */
  blurb: string;
  /** Single read-only statement (SELECT / WITH only). DuckDB SQL dialect. */
  sql: string;
}

export interface PresetGroup {
  /** Section heading (persona / question category). */
  title: string;
  /** Section subtitle — one phrase describing the category. */
  subtitle: string;
  presets: Preset[];
}

// ---- Reusable SQL fragments ------------------------------------------------

/** Winner + runner-up join. Used by every "margin" preset. */
const WR_JOIN = `
FROM constituencies c
JOIN candidates w  ON w.ac_eci_no  = c.ac_eci_no AND w.is_winner = 1
JOIN candidates r2 ON r2.ac_eci_no = c.ac_eci_no AND r2.rank = 2`;

/** Canonical eight-column projection for the "margin" preset family. */
const WR_COLS = `
  c.ac_eci_no,
  c.name        AS constituency,
  w.name        AS winner,
  w.party_short AS win_party,
  r2.name       AS runner_up,
  r2.party_short AS ru_party,
  w.votes - r2.votes AS margin_votes,
  ROUND(100.0 * (w.votes - r2.votes) / NULLIF(c.votes_polled, 0), 2) AS margin_pct`;

// ---- Catalog ---------------------------------------------------------------

export const PRESET_GROUPS: PresetGroup[] = [
  {
    title: "Headlines",
    subtitle: "Stories a journalist would lead with.",
    presets: [
      {
        id: "closest",
        label: "Closest 10 contests",
        blurb: "Tightest margins — recount territory.",
        sql: `SELECT${WR_COLS}${WR_JOIN}
ORDER BY margin_votes ASC
LIMIT 10;`,
      },
      {
        id: "biggest",
        label: "Top 10 winning margins",
        blurb: "Largest margins (votes).",
        sql: `SELECT${WR_COLS}${WR_JOIN}
ORDER BY margin_votes DESC
LIMIT 10;`,
      },
      {
        id: "nota_decisive",
        label: "NOTA exceeded the margin",
        blurb: "Seats where NOTA votes were larger than the winning margin.",
        sql: `SELECT${WR_COLS},
  n.votes AS nota_votes,
  ROUND(n.vote_share_pct, 2) AS nota_pct${WR_JOIN}
JOIN candidates n ON n.ac_eci_no = c.ac_eci_no AND n.is_nota = 1
WHERE n.votes > (w.votes - r2.votes)
ORDER BY (w.votes - r2.votes) ASC;`,
      },
      {
        id: "independents_won",
        label: "Independents who won",
        blurb: "Winners with no ECI party code.",
        sql: `SELECT${WR_COLS}${WR_JOIN}
WHERE w.party_eci_code IS NULL AND w.is_nota = 0
ORDER BY margin_votes DESC;`,
      },
      {
        id: "low_share_winners",
        label: "Winners under 30% vote share",
        blurb: "Fragmented mandates — winner pulled in less than a third of votes polled.",
        sql: `SELECT${WR_COLS},
  ROUND(w.vote_share_pct, 2) AS winner_share_pct${WR_JOIN}
WHERE w.vote_share_pct < 30
ORDER BY w.vote_share_pct ASC;`,
      },
      {
        id: "dominant_wins",
        label: "Dominant wins (>60% share)",
        blurb: "Strongholds — winners crossed 60% vote share.",
        sql: `SELECT${WR_COLS},
  ROUND(w.vote_share_pct, 2) AS winner_share_pct${WR_JOIN}
WHERE w.vote_share_pct > 60
ORDER BY w.vote_share_pct DESC;`,
      },
    ],
  },
  {
    title: "Party performance",
    subtitle: "How each contender did across the state.",
    presets: [
      {
        id: "party_totals",
        label: "Seats and vote share by party",
        blurb: "Seats won, total votes, and statewide vote share.",
        sql: `WITH valid AS (
  SELECT SUM(votes) AS total FROM candidates WHERE is_nota = 0
)
SELECT
  party_short,
  COUNT(*) FILTER (WHERE is_winner = 1) AS seats_won,
  SUM(votes)                            AS votes,
  ROUND(100.0 * SUM(votes) / (SELECT total FROM valid), 2) AS vote_share_pct
FROM candidates
WHERE is_nota = 0
GROUP BY party_short
ORDER BY seats_won DESC, votes DESC;`,
      },
      {
        id: "strike_rate",
        label: "Party strike rate",
        blurb: "Seats contested, seats won, and conversion %.",
        sql: `SELECT
  party_short,
  COUNT(*)                              AS contested,
  SUM(is_winner)                        AS won,
  ROUND(100.0 * SUM(is_winner) / COUNT(*), 2) AS strike_rate_pct
FROM candidates
WHERE is_nota = 0
GROUP BY party_short
HAVING contested >= 5
ORDER BY strike_rate_pct DESC, won DESC;`,
      },
      {
        id: "party_safest",
        label: "Safest seat for each party",
        blurb: "Each winning party's largest-margin seat.",
        sql: `WITH wins AS (
  SELECT
    c.ac_eci_no, c.name AS constituency,
    w.name AS winner, w.party_short AS win_party,
    r2.name AS runner_up, r2.party_short AS ru_party,
    w.votes - r2.votes AS margin_votes,
    ROUND(100.0 * (w.votes - r2.votes) / NULLIF(c.votes_polled, 0), 2) AS margin_pct,
    ROW_NUMBER() OVER (PARTITION BY w.party_short ORDER BY w.votes - r2.votes DESC) AS rk
  ${WR_JOIN.trim()}
)
SELECT ac_eci_no, constituency, winner, win_party, runner_up, ru_party, margin_votes, margin_pct
FROM wins
WHERE rk = 1
ORDER BY margin_votes DESC;`,
      },
      {
        id: "party_vulnerable",
        label: "Most vulnerable seat for each party",
        blurb: "Each winning party's narrowest hold.",
        sql: `WITH wins AS (
  SELECT
    c.ac_eci_no, c.name AS constituency,
    w.name AS winner, w.party_short AS win_party,
    r2.name AS runner_up, r2.party_short AS ru_party,
    w.votes - r2.votes AS margin_votes,
    ROUND(100.0 * (w.votes - r2.votes) / NULLIF(c.votes_polled, 0), 2) AS margin_pct,
    ROW_NUMBER() OVER (PARTITION BY w.party_short ORDER BY w.votes - r2.votes ASC) AS rk
  ${WR_JOIN.trim()}
)
SELECT ac_eci_no, constituency, winner, win_party, runner_up, ru_party, margin_votes, margin_pct
FROM wins
WHERE rk = 1
ORDER BY margin_votes ASC;`,
      },
    ],
  },
  {
    title: "Contests & candidates",
    subtitle: "Drill into individual races and candidates.",
    presets: [
      {
        id: "top_vote_getters",
        label: "Top vote-getting candidates",
        blurb: "Highest individual vote totals across the state (top 15).",
        sql: `SELECT
  c.ac_eci_no,
  c.name AS constituency,
  cand.name AS candidate,
  cand.party_short,
  cand.votes,
  ROUND(cand.vote_share_pct, 2) AS vote_share_pct,
  cand.is_winner
FROM candidates cand
JOIN constituencies c ON c.ac_eci_no = cand.ac_eci_no
WHERE cand.is_nota = 0
ORDER BY cand.votes DESC
LIMIT 15;`,
      },
      {
        id: "triangular",
        label: "Three-cornered contests",
        blurb: "Seats where the top 3 finished within 5 percentage points of each other.",
        sql: `WITH top3 AS (
  SELECT ac_eci_no,
         MAX(CASE WHEN rank = 1 THEN vote_share_pct END) AS s1,
         MAX(CASE WHEN rank = 2 THEN vote_share_pct END) AS s2,
         MAX(CASE WHEN rank = 3 THEN vote_share_pct END) AS s3
  FROM candidates
  WHERE is_nota = 0 AND rank <= 3
  GROUP BY ac_eci_no
)
SELECT
  c.ac_eci_no, c.name AS constituency,
  ROUND(s1, 2) AS first_pct,
  ROUND(s2, 2) AS second_pct,
  ROUND(s3, 2) AS third_pct,
  ROUND(s1 - s3, 2) AS spread_pct
FROM top3 t
JOIN constituencies c ON c.ac_eci_no = t.ac_eci_no
WHERE s3 IS NOT NULL AND (s1 - s3) <= 5
ORDER BY spread_pct ASC;`,
      },
      {
        id: "nota_top",
        label: "Highest NOTA share (top 10)",
        blurb: "Where voters most often picked None Of The Above.",
        sql: `SELECT
  c.ac_eci_no,
  c.name AS constituency,
  ROUND(n.vote_share_pct, 2) AS nota_pct,
  n.votes AS nota_votes
FROM constituencies c
JOIN candidates n ON n.ac_eci_no = c.ac_eci_no AND n.is_nota = 1
ORDER BY n.vote_share_pct DESC
LIMIT 10;`,
      },
      {
        id: "head_to_head",
        label: "Head-to-head: rank-1 vs rank-2 party pairs",
        blurb: "How often each pair of parties faced off in the top two.",
        sql: `WITH pairs AS (
  SELECT
    LEAST(w.party_short, r2.party_short) AS party_a,
    GREATEST(w.party_short, r2.party_short) AS party_b,
    CASE WHEN w.party_short < r2.party_short THEN 1 ELSE 0 END AS a_won
  ${WR_JOIN.trim()}
)
SELECT
  party_a, party_b,
  COUNT(*) AS contests,
  SUM(a_won)              AS a_wins,
  COUNT(*) - SUM(a_won)   AS b_wins
FROM pairs
GROUP BY party_a, party_b
HAVING contests >= 3
ORDER BY contests DESC;`,
      },
    ],
  },
  {
    title: "Distribution",
    subtitle: "Statewide shape of the result.",
    presets: [
      {
        id: "candidates_per_ac",
        label: "Candidates per constituency",
        blurb: "Mean, minimum and maximum candidate count (excluding NOTA).",
        sql: `SELECT
  ROUND(AVG(n), 2) AS avg_candidates,
  MIN(n)           AS min_candidates,
  MAX(n)           AS max_candidates
FROM (
  SELECT ac_eci_no, COUNT(*) AS n
  FROM candidates
  WHERE is_nota = 0
  GROUP BY ac_eci_no
);`,
      },
      {
        id: "margin_buckets",
        label: "Seats by margin band",
        blurb: "How many seats were decided by < 2.5%, 2.5–5%, 5–10%, 10–20%, > 20%.",
        sql: `WITH m AS (
  SELECT 100.0 * (w.votes - r2.votes) / NULLIF(c.votes_polled, 0) AS pct
  ${WR_JOIN.trim()}
)
SELECT
  CASE
    WHEN pct < 2.5  THEN '1. < 2.5%'
    WHEN pct < 5    THEN '2. 2.5 – 5%'
    WHEN pct < 10   THEN '3. 5 – 10%'
    WHEN pct < 20   THEN '4. 10 – 20%'
    ELSE                 '5. > 20%'
  END AS margin_band,
  COUNT(*) AS seats
FROM m
GROUP BY margin_band
ORDER BY margin_band;`,
      },
      {
        id: "winner_share_buckets",
        label: "Winners by vote share band",
        blurb: "How many seats were won at <30%, 30–40%, 40–50%, 50–60%, >60% share.",
        sql: `SELECT
  CASE
    WHEN vote_share_pct < 30 THEN '1. < 30%'
    WHEN vote_share_pct < 40 THEN '2. 30 – 40%'
    WHEN vote_share_pct < 50 THEN '3. 40 – 50%'
    WHEN vote_share_pct < 60 THEN '4. 50 – 60%'
    ELSE                          '5. > 60%'
  END AS share_band,
  COUNT(*) AS seats
FROM candidates
WHERE is_winner = 1
GROUP BY share_band
ORDER BY share_band;`,
      },
    ],
  },
];

/** Flat preset list. Order matches the catalog above. */
export const ALL_PRESETS: Preset[] = PRESET_GROUPS.flatMap(g => g.presets);

/** Lookup by id; returns undefined if unknown. */
export function findPreset(id: string): Preset | undefined {
  return ALL_PRESETS.find(p => p.id === id);
}
