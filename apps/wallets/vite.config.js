import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { resolve } from "path";

export default defineConfig({
  base: "/wallets/",
  plugins: [react()],
  appType: "mpa",
  build: {
    rollupOptions: {
      input: {
        main: resolve(__dirname, "index.html"),
        packs: resolve(__dirname, "packs/index.html"),
      },
    },
  },
  server: {
    port: 3000,
    proxy: {
      "/wallet-api": {
        target: process.env.VITE_PROXY_TARGET || "https://api.frong.ai",
        changeOrigin: true,
        secure: true,
        rewrite: (p) => p.replace(/^\/wallet-api/, ""),
      },
    },
  },
});
