// ChartShell — barrel.
//
// Re-exports the contract so callers can `import { ChartShellActionSpec,
// filterAllowedActions } from "./charts/chart-shell"` rather than
// reaching into the file layout. The Svelte renderer lives one level up
// at `frontend/src/lib/charts/ChartShell.svelte` and is imported by
// Svelte module resolution, not from this barrel.

export {
  ALLOWED_ACTIONS,
  filterAllowedActions,
  sortActionsForFooter,
} from "./actions";

export type {
  ChartShellAction,
  ChartShellActionSpec,
  ChartShellHonestyBanner,
  ChartShellHonestyKind,
  SourceV2Row,
} from "./types";
