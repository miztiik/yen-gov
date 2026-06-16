/**
 * Citizen-facing party-recognition vocabulary (Hans H7).
 *
 * Extracted in Wave-F F6 from `PartyAboutCard.svelte` so the helper
 * survives the AboutCard RIP (the card collapses into the per-party
 * header in Wave-F F6 per `TODO/20260615-party-page-citizen-fixes-plan.md`).
 *
 * The vocabulary widens the prior "party" copy into a fuller phrase
 * that disambiguates the legal category from the noun-as-party (so a
 * citizen scanning the page knows "Nationally recognised party" is an
 * ECI legal class, not a value judgment). Sentinel rows (IND, NOTA)
 * surface as "Special category" — the prior "Special" was too terse
 * and read as a UX easter egg rather than an honest data-class.
 *
 * Pure; pinned by `recognition-label.test.ts`.
 */
export function recognitionLabel(scope: string | null): string {
  switch (scope) {
    case "national":
      return "Nationally recognised party";
    case "state":
      return "State-recognised party";
    case "unrecognised_registered":
      return "Registered party (unrecognised)";
    case "defunct":
      return "Defunct";
    case "sentinel":
      return "Special category";
    default:
      return "Recognition unknown";
  }
}
