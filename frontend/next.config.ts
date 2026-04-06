import type { NextConfig } from "next";
import path from "path";
import createNextIntlPlugin from 'next-intl/plugin';

const frontendDir = import.meta.dirname;

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000";

const nextConfig: NextConfig = {
  output: 'standalone',
  turbopack: {
    root: frontendDir,
    resolveAlias: {
      tailwindcss: path.resolve(frontendDir, "node_modules/tailwindcss"),
      "tw-animate-css": path.resolve(frontendDir, "node_modules/tw-animate-css"),
    },
  },
  async rewrites() {
    return [
      // Proxy /api/config/* to backend (not handled by Next.js API routes)
      {
        source: "/api/config/:path*",
        destination: `${BACKEND_URL}/api/config/:path*`,
      },
    ];
  },
};

const withNextIntl = createNextIntlPlugin('./src/i18n/request.ts');
export default withNextIntl(nextConfig);
