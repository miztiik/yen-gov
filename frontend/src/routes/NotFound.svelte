<!--
  404 page.

  Copy follows the rip-and-replace URL grammar handover (§7): the citizen
  who landed here probably followed a stale link from before the IA
  reset. Tell them that, then offer the two most useful destinations:
  the home page, and the topics index — which lets them browse the
  catalogue and find the new home of whatever they were looking for.

  We deliberately keep this page minimal: no "did you mean..." fuzzy
  matcher, no full sitemap. Two anchors is enough to recover; the
  catalogue at /t is the discovery surface.
-->
<script lang="ts">
  import { link } from "../lib/links";
  interface Props { params: { path: string } }
  let { params }: Props = $props();
</script>

<main class="max-w-md mx-auto p-12 text-center space-y-4">
  <h1 class="text-3xl font-bold">404</h1>
  <p class="text-slate-600">
    This page has moved. We recently reorganised yen-gov's URL structure.
  </p>
  <p class="text-slate-500 text-sm">
    No route matches <code class="font-mono">{params.path}</code>.
  </p>
  <nav class="flex justify-center gap-4 pt-2">
    <a class="text-blue-600 hover:underline" href={link.home()}>← Home</a>
    <a class="text-blue-600 hover:underline" href={link.topics()}>Browse topics</a>
  </nav>
</main>
