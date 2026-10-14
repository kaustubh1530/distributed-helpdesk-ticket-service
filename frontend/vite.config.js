import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],

  server: {
    proxy: {
      "/api/8000": {
        target: "http://localhost:8000",
        changeOrigin: true,
        rewrite: (path) =>
          path.replace(/^\/api\/8000/, ""),
      },

      "/api/8001": {
        target: "http://localhost:8001",
        changeOrigin: true,
        rewrite: (path) =>
          path.replace(/^\/api\/8001/, ""),
      },

      "/api/8002": {
        target: "http://localhost:8002",
        changeOrigin: true,
        rewrite: (path) =>
          path.replace(/^\/api\/8002/, ""),
      },
    },
  },
});