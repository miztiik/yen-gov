// Public surface of the SourceList v2 module.
//
// Consumers should import from `frontend/src/lib/source-list-v2` rather
// than the individual files so the internal layout stays refactorable.
//
// The render surface (`SourceList.svelte` v2) is a separate follow-up;
// this PR ships only the contract + pure helpers.

export type {
  CollapsedSummary,
  ConfidenceTier,
  ExpandedDisclosure,
  SourceLicense,
  SourceV2Row,
  VerificationMethod,
} from "./types";

export { FORBIDDEN_SOURCE_FIELDS } from "./types";

export {
  composeDefaultCitation,
  formatCollapsedSummary,
  formatExpandedDisclosure,
  verificationMethodRank,
} from "./format";
