// Canned InsightIntent fixtures for PR-1 (post-F1.3b cutover).
//
// Per plan-doc §17 D-10: PR-1 ships ZERO model code. The Yenask.svelte UI
// only knows how to execute these four fixed intents (clickable buttons).
// Phase 2 (PR-2) replaces the buttons with a free-text input wired to a
// model adapter - but the same four intents survive as evaluation cases.
//
// All four intents are scoped to the Tamil Nadu AC General April 2021 slice
// because that's the deepest TCPD per-(state, year) CSV partition that
// exists on disk today (TN-2026 CSV has NOT been emitted; F1.3b reader
// flip would 404 against `state=tamil-nadu/election=2026/candidacies.csv`).
// When the TN-2026 backfill lands a separate canned intent set can be
// added for AcGenMay2026.
//
// Adding a fifth canned intent here is a 1-line edit; the compiler must
// already support the concept_id (see compile-intent.ts dispatch).

import type { InsightIntent } from "../contracts/insight-intent";
import { parseInsightIntent } from "../contracts/insight-intent";

const RAW_CANNED_INTENTS: ReadonlyArray<{
  readonly id: string;
  readonly label: string;
  readonly description: string;
  readonly intent: InsightIntent;
}> = [
  {
    id: "tn-apr-2021-party-totals",
    label: "Which parties won the most seats?",
    description:
      "DMK / AIADMK / BJP / INC totals for the Tamil Nadu AC General April 2021 cohort.",
    intent: parseInsightIntent({
      version: "insight.intent.v0",
      question: "Which parties won the most seats in Tamil Nadu's April 2021 assembly election?",
      concept_id: "party_totals",
      filters: {
        state_partition_id: "tamil-nadu",
        period_label: "AcGenApr2021",
        limit: 10,
      },
      reasoning:
        "Group ECI assembly results by winning party for the named period and rank descending.",
    }),
  },
  {
    id: "tn-apr-2021-closest-contests",
    label: "Which seats were closest?",
    description:
      "Top 10 narrowest victory margins (winner vs runner-up percentage gap) in TN April 2021.",
    intent: parseInsightIntent({
      version: "insight.intent.v0",
      question: "Which Tamil Nadu seats were decided by the narrowest margins in April 2021?",
      concept_id: "closest_contests",
      filters: {
        state_partition_id: "tamil-nadu",
        period_label: "AcGenApr2021",
        limit: 10,
      },
      reasoning:
        "Compute per-AC winner vs runner-up vote-share gap, ascending; smallest gap = closest.",
    }),
  },
  {
    id: "tn-apr-2021-ac-167-mylapore",
    label: "What happened in AC 167 (Mylapore)?",
    description:
      "Top-5 candidates + collapsed others for the Mylapore seat in TN April 2021.",
    intent: parseInsightIntent({
      version: "insight.intent.v0",
      question: "What were the results in Mylapore (AC 167) in the Tamil Nadu April 2021 election?",
      concept_id: "constituency_result",
      filters: {
        state_partition_id: "tamil-nadu",
        period_label: "AcGenApr2021",
        ac_no: 167,
      },
      reasoning:
        "Read the per-AC result row for ac_no 167 in the named period; surface top-5 (the project-wide presentation default, inlined as _TOP_N_DEFAULT in backend/yen_gov/cli.py since G9 2026-06-08).",
    }),
  },
  {
    id: "tn-apr-2021-turnout-extremes",
    label: "Highest and lowest turnout seats?",
    description:
      "Top-10 highest + lowest turnout ACs in TN April 2021, side by side.",
    intent: parseInsightIntent({
      version: "insight.intent.v0",
      question: "Which Tamil Nadu seats saw the highest and lowest turnout in April 2021?",
      concept_id: "turnout_extremes",
      filters: {
        state_partition_id: "tamil-nadu",
        period_label: "AcGenApr2021",
        limit: 10,
      },
      reasoning:
        "Order ACs by per-AC turnout percentage; surface top-N and bottom-N as two ranked lists.",
    }),
  },
] as const;

/**
 * Read-only registry of the canned intents the PR-1 UI exposes. The
 * `parseInsightIntent` call above doubles as a build-time invariant: a
 * malformed fixture fails the module import, so vitest catches it.
 */
export const CANNED_INTENTS = RAW_CANNED_INTENTS;

/**
 * Find a canned intent by id. Used by Playwright e2e to drive a specific
 * fixture deterministically.
 */
export function getCannedIntent(id: string): InsightIntent | undefined {
  return CANNED_INTENTS.find(c => c.id === id)?.intent;
}
