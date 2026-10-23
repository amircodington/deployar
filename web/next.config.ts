import type { NextConfig } from "next";

// The browser only ever talks to this origin; /api is proxied to the agent on the host, so the
// session cookie stays same-origin and nothing is fetched from outside (CLAUDE.md rule 5).
const agentUrl = process.env.AGENT_URL ?? "http://localhost:8800";

const nextConfig: NextConfig = {
  output: "standalone", // the production image (root Dockerfile) runs .next/standalone/server.js
  // gzip buffers the proxied SSE stream until the run ends; this app is served on localhost only.
  compress: false,
  cacheComponents: true,
  partialPrefetching: true,
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${agentUrl}/api/:path*` }];
  },
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
