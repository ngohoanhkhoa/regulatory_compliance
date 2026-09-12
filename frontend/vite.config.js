import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "^(/auth|/chat|/query|/acts|/history|/feedback|/health|/api)": {
        target: "http://localhost:8000",
        bypass(req) {
          if (req.headers.accept?.includes("text/html")) {
            return "/index.html";
          }
        },
      },
    },
  },
  build: { outDir: "dist" },
});
