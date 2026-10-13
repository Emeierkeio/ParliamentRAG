import type { NextConfig } from "next";

// The operational tool moved to Fascicoli.
const FASCICOLI_URL = 'https://www.fascicoli.it';
const MOVED_TO_FASCICOLI = [
  '/iswc',
  '/home',
  '/chat',
  '/tema',
  '/timeline',
  '/parlamentari',
  '/gruppi',
  '/ranking',
  '/compass',
  '/search',
  '/explorer',
  '/valutazione',
];

// Pages of the previous site (Italian and English shared one URL) and of the
// static prototype (*.html), with their new address.
const OLD_PAGES: [string, string][] = [
  ['/method', '/metodo'],
  ['/data', '/dati'],
  ['/pubblicazioni', '/ricerca'],
  ['/sistemi', '/#sistemi'],
  ['/index.html', '/'],
  ['/metodo.html', '/metodo'],
  ['/verifica.html', '/verifica'],
  ['/dati.html', '/dati'],
  ['/ricerca.html', '/ricerca'],
  ['/sviluppatori.html', '/sviluppatori'],
  ['/aggiornamenti.html', '/aggiornamenti'],
  ['/privacy.html', '/privacy'],
  ['/termini.html', '/termini'],
  // Italian slugs typed under /en
  ['/en/metodo', '/en/method'],
  ['/en/verifica', '/en/verification'],
  ['/en/dati', '/en/data'],
  ['/en/ricerca', '/en/research'],
  ['/en/pubblicazioni', '/en/research'],
  ['/en/sviluppatori', '/en/developers'],
  ['/en/aggiornamenti', '/en/updates'],
  ['/en/termini', '/en/terms'],
  ['/en/sistemi', '/en#sistemi'],
  ['/it', '/'],
];

const nextConfig: NextConfig = {
  output: 'standalone',
  async headers() {
    return [
      // Font files never change under the same name
      {
        source: '/sito/font/:file*',
        headers: [{ key: 'Cache-Control', value: 'public, max-age=31536000, immutable' }],
      },
      ...(process.env.NOINDEX === "1"
        ? [{ source: "/:path*", headers: [{ key: "X-Robots-Tag", value: "noindex, nofollow" }] }]
        : []),
    ];
  },
  async redirects() {
    return [
      // Canonical host: the apex domain redirects to www
      {
        source: '/:path*',
        has: [{ type: 'host', value: 'parliamentrag.it' }],
        destination: 'https://www.parliamentrag.it/:path*',
        permanent: true,
      },
      // Hand-off links from Stenografo still landing on the root belong to
      // Fascicoli now; the query string (q, utm_*) is carried over.
      {
        source: '/',
        has: [{ type: 'query', key: 'q' }],
        destination: `${FASCICOLI_URL}/home`,
        permanent: false,
      },
      // `:path*` also matches the bare route.
      ...MOVED_TO_FASCICOLI.map((route) => ({
        source: `${route}/:path*`,
        destination: `${FASCICOLI_URL}${route}/:path*`,
        permanent: false,
      })),
      ...OLD_PAGES.map(([source, destination]) => ({ source, destination, permanent: true })),
    ];
  },
};

export default nextConfig;
