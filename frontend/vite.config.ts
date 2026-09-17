import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

const atlasGatewayToken = process.env.ATLAS_GATEWAY_TOKEN ?? "";
const atlasUsername = process.env.ATLAS_USERNAME ?? "developer";
const atlasDevAllowedHosts = (process.env.ATLAS_DEV_ALLOWED_HOSTS ?? "")
  .split(",")
  .map((host) => host.trim())
  .filter(Boolean);
const operationGateway = {
  target: "http://127.0.0.1:8002",
  changeOrigin: true,
  headers: {
    "X-Atlas-Gateway-Token": atlasGatewayToken,
    "X-Atlas-Authenticated": atlasUsername,
  },
  configure: (proxy: { on: (event: string, handler: (proxyRequest: { setHeader: (name: string, value: string) => void }, request: { headers: { host?: string } }) => void) => void }) => {
    proxy.on("proxyReq", (proxyRequest, request) => {
      if (request.headers.host) proxyRequest.setHeader("X-Forwarded-Host", request.headers.host);
    });
  },
};

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    allowedHosts: atlasDevAllowedHosts.length ? atlasDevAllowedHosts : undefined,
    proxy: {
      "/api/database": {
        target: "http://127.0.0.1:8100",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/database/, ""),
      },
      "/api/dictionary": {
        target: "http://127.0.0.1:8001",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/dictionary/, ""),
      },
      "/api/translator": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/translator/, ""),
      },
      "/api/services": {
        ...operationGateway,
        rewrite: (path) => path.replace(/^\/api\/services/, ""),
      },
      "/api/operations": {
        ...operationGateway,
        rewrite: (path) => path.replace(/^\/api\/operations/, "/operations"),
      },
      "/api/maintenance": {
        ...operationGateway,
        rewrite: (path) => path.replace(/^\/api\/maintenance/, "/maintenance"),
      },
      "/api/gemma": {
        ...operationGateway,
        rewrite: (path) => path.replace(/^\/api\/gemma/, "/gemma"),
      },
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: "./src/test/setup.ts",
  },
});
