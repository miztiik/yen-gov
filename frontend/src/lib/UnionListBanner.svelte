<script lang="ts">
  // Union-list ranking banner.
  //
  // Per ADR-0022 (Governance Strategist hard line): cross-state ranking on
  // a Union-list subject MUST carry an explicit notice that the subject is
  // administered by the Government of India, so state-level variation
  // reflects implementation, not policy authority. Without this banner a
  // ranked choropleth on (say) "highway-km per state" silently invites the
  // citizen to credit/blame the wrong government.
  //
  // Render-only. Takes the topic title for the contextualised copy; emits
  // nothing else. Caller decides where to place it (typically immediately
  // under the topic header on `/t/:topic`).

  interface Props {
    /** Title of the topic, used in the body copy ("This subject (X) is..."). */
    topic_title: string;
  }

  let { topic_title }: Props = $props();
</script>

<aside
  data-unionlistbanner
  class="rounded border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900 mb-4"
>
  <p class="m-0">
    <strong class="font-semibold">Union-list subject.</strong>
    {topic_title} is administered by the Government of India under the Seventh Schedule
    Union List. State-level variation shown here reflects implementation, geography, or
    historical investment — not policy authority.
  </p>
</aside>
