import type { NextConfig } from "next";
import createNextIntlPlugin from 'next-intl/plugin';

const nextConfig: NextConfig = {
  output: 'standalone',
  async redirects() {
    return [
      // Canonical host: the apex domain redirects to www
      {
        source: '/:path*',
        has: [{ type: 'host', value: 'parliamentrag.it' }],
        destination: 'https://www.parliamentrag.it/:path*',
        permanent: true,
      },
    ];
  },
};

const withNextIntl = createNextIntlPlugin('./src/i18n/request.ts');
export default withNextIntl(nextConfig);
