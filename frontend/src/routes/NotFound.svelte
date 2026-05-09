<script lang="ts">
  interface Props { params: { path: string } }
  let { params }: Props = $props();
</script>

<main class="max-w-md mx-auto p-12 text-center space-y-3">
  <h1 class="text-3xl font-bold">404</h1>
  <p class="text-slate-500">No route matches <code class="font-mono">{params.path}</code>.</p>
  <p><a class="text-blue-600 hover:underline" href="#/">← Home</a></p>
</main>
