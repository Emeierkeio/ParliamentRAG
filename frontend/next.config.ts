import type { NextConfig } from "next";
import path from "path";
import createNextIntlPlugin from 'next-intl/plugin';

const frontendDir = import.meta.dirname;

const nextConfig: NextConfig = {
  output: 'standalone',
  turbopack: {
    root: frontendDir,
    resolveAlias: {
      tailwindcss: path.resolve(frontendDir, "node_modules/tailwindcss"),
      "tw-animate-css": path.resolve(frontendDir, "node_modules/tw-animate-css"),
    },
  },
};

const withNextIntl = createNextIntlPlugin('./src/i18n/request.ts');
export default withNextIntl(nextConfig);
