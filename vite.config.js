import { defineConfig } from "vite";

const API = process.env.FRONG_API || "http://127.0.0.1:8787";

export default defineConfig({
  build: {
    target: "es2022",
  },
  server: {
    port: 5175,
    proxy: {
      "/api": { target: API, changeOrigin: true },
      "/auth": { target: API, changeOrigin: true },
      "/health": { target: API, changeOrigin: true },
    },
  },
});
