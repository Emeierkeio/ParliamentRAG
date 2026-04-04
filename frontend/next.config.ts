import type { NextConfig } from "next";
import path from "path";

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

export default nextConfig;
