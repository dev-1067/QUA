import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: "autoUpdate",
      includeAssets: ["favicon.svg", "india-states.geojson"],
      manifest: {
        name: "RecoverIQ Field",
        short_name: "RecoverIQ",
        description: "Collections worklist that keeps working offline",
        start_url: "/agent",
        display: "standalone",
        background_color: "#0f1d19",
        theme_color: "#0f1d19",
        icons: [
          { src: "/icon-192.png", sizes: "192x192", type: "image/png" },
          { src: "/icon-512.png", sizes: "512x512", type: "image/png" },
        ],
      },
      workbox: {
        navigateFallback: "/index.html",
        navigateFallbackDenylist: [/^\/api\//],
        globPatterns: ["**/*.{js,css,html,svg,png,woff2,geojson}"],
        maximumFileSizeToCacheInBytes: 4 * 1024 * 1024,
      },
    }),
  ],
  server: {
    port: 5173,
    proxy: { "/api": { target: "http://127.0.0.1:8000", ws: true, changeOrigin: false } },
  },
  build: { outDir: "../backend/static", emptyOutDir: true, chunkSizeWarningLimit: 1500 },
});
