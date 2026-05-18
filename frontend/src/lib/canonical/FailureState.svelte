<script lang="ts">
  // FailureState — renders a LoaderResult.failed (or a ManifestError) as
  // citizen-facing copy. SINGLE component every canonical-store-backed
  // view-model uses; no view should hand-roll its own failure UI.
  //
  // Contract (canonical-store.md §16):
  //   - plain-language headline + body, never the raw error message
  //   - Retry button shown only when the error kind is transient
  //     (network / schema_version_unsupported). Terminal kinds get no
  //     button — retrying would be a lie.
  //   - no stack traces, no URLs, no version strings ever rendered.

  import { copyForError, type FailureCopy } from "./failure-state";
  import type { ManifestError } from "./types";

  interface Props {
    error: ManifestError;
    /** Called when the citizen taps Retry. Component never decides what
     *  retry means — that's the caller's loader concern. */
    onRetry?: () => void;
  }

  const { error, onRetry }: Props = $props();
  const copy: FailureCopy = $derived(copyForError(error));
</script>

<div
  class="rounded-md border border-slate-200 bg-white px-4 py-6 text-center"
  data-testid="canonical-failure-state"
  data-error-kind={error.kind}
>
  <p class="text-base font-medium text-slate-800">{copy.headline}</p>
  {#if copy.body}
    <p class="mt-1 text-sm text-slate-600">{copy.body}</p>
  {/if}
  {#if copy.showRetry && onRetry}
    <button
      type="button"
      class="mt-4 inline-flex items-center rounded-md border border-slate-300 bg-slate-50 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-100"
      onclick={onRetry}
      data-testid="canonical-failure-retry"
    >
      Try again
    </button>
  {/if}
</div>
