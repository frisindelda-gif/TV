import path from "node:path";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Tudo local: o dev server só escuta em 127.0.0.1 e encaminha /api para o backend FastAPI.
export default defineConfig({
  plugins: [react()],
  resolve: { alias: { "@": path.resolve(__dirname, "./src") } },
  server: {
    host: "127.0.0.1",
    port: 5173,
    proxy: { "/api": "http://127.0.0.1:8727" },
  },
});
