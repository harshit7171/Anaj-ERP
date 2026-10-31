import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const obfuscate = process.env.ANAJ_BUILD_OBFUSCATE === "1";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  esbuild: obfuscate
    ? {
        legalComments: "none",
        minifyIdentifiers: true,
        minifySyntax: true,
        minifyWhitespace: true,
      }
    : undefined,
  root: ".",
  publicDir: "frontend/public",
  base: "./",
  build: {
    outDir: "frontend/dist",
    emptyOutDir: true,
  },
  server: {
    port: 5173,
    strictPort: true,
  },
});
