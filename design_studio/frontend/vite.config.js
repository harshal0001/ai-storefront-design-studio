import { cwd } from "node:process";
import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, cwd(), "VITE_");
  const apiTarget = env.VITE_API_TARGET || "http://localhost:8000";
  const originSecret = env.VITE_CF_ORIGIN_SECRET || "";

  return {
    plugins: [react()],
    server: {
      port: 5173,
      proxy: {
        "/api": {
          target: apiTarget,
          changeOrigin: true,
          ...(originSecret && {
            headers: { "x-cf-origin-secret": originSecret },
          }),
        },
      },
    },
  };
});
