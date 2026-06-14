// PR-2 of TODO/20260614-party-page-reimagination-plan.md.
//
// `cleanNote(rawNote)` - pure, idempotent helper that strips
// operator-narrative leaks from a `methodology_breaks.json` row's
// `note` field before it reaches the citizen-facing tooltip.
//
// The citizen-facing chart on /parties/<slug> renders the hovered
// marker's `note` verbatim. Several upstream rows historically
// carried operator-only narrative tails (`PR-4 of TODO/...md`,
// `lspc-delim-1976`, `methodology_version=...`) that leaked the
// repo's authoring grammar into the tooltip.
//
// PR-2 closes the leak at two seams: the JSON itself is hand-scrubbed
// (the source-of-truth fix), AND this helper runs at the view-model
// fetch boundary as defense-in-depth so any future regression in the
// JSON is filtered before reaching the renderer. The contract test
// `frontend/src/contracts/methodology-tooltip-no-leaks.test.ts`
// asserts BOTH the on-disk file is clean AND cleanNote is idempotent
// on clean input.

/** Scrub operator-narrative patterns from a methodology-break note.
 *  Idempotent: `cleanNote(cleanNote(x)) === cleanNote(x)` for every
 *  string `x` that does not strip to empty. Throws when the input
 *  contains nothing but operator narrative (caller fed a leak-only
 *  row, which is a structural data bug worth surfacing loudly). */
export function cleanNote(rawNote: string): string {
  const stripped = rawNote
    // " PR-N of TODO/<path>.<ext>[ (parenthetical)]. " - full sentence
    .replace(
      /\s*PR-\d+\s+of\s+TODO\/[\w-]+(?:\/[\w-]+)*(?:\.\w+)?(?:\s+\([^)]*\))?[^.]*\.\s*/g,
      " ",
    )
    // " PR-N will render the marker on Component. " - full sentence
    .replace(/\s*PR-\d+\s+will\s+[^.]*\.\s*/g, " ")
    // " - added alongside lspc-delim-... chain is represented. " - em-dash narrative
    .replace(/\s*[-\u2014]\s*added\s+alongside\s+lspc-delim-[^.]*\.\s*/gi, " ")
    // Bare repo-grammar tokens that may survive sentence-level scrubs
    .replace(/\bTODO\/[\w-]+(?:\/[\w-]+)*\.\w+\b/g, "")
    .replace(/\bPR-\d+\b/g, "")
    .replace(/\blspc-delim-\d+\b/g, "")
    .replace(/\bmethodology_version[:=]\s*\S+/g, "")
    // Whitespace cleanup AFTER scrub so " . " collapses to "."
    .replace(/\s+([,.;])/g, "$1")
    .replace(/\s{2,}/g, " ")
    .trim();
  if (stripped.length === 0) {
    throw new Error(
      `methodology-break note stripped to empty (input was '${rawNote}')`,
    );
  }
  return stripped;
}
