/** @type {import("tailwindcss").Config} */
// Darker palette than the public app — visual cue that you're in the
// operator console (the public app is light/slate; admin is slate-900).
export default {
  content: ["./index.html", "./src/**/*.{svelte,ts,js}"],
  theme: { extend: {} },
  plugins: [],
};
