import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  // The build goes inside the Python package, where `slugline serve` finds it.
  build: { outDir: "../src/slugline/static", emptyOutDir: true },
  // `npm run dev` talks to a `slugline serve` running on its default port.
  server: { proxy: { "/api": "http://127.0.0.1:8000" } },
});
