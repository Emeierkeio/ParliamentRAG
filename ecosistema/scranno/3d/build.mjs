// Bundle della vista 3D: node ecosistema/scranno/3d/build.mjs
// Richiede esbuild (npx esbuild o una copia locale) e scranno/node_modules (three 0.186.1).
// ESBUILD=/percorso/node_modules/esbuild/lib/main.js se esbuild non è installato qui
const { build } = await import(process.env.ESBUILD || 'esbuild');
import { fileURLToPath } from 'node:url';
import path from 'node:path';
const qui = path.dirname(fileURLToPath(import.meta.url));
const radice = path.resolve(qui, '../../..');
await build({
  entryPoints: [path.join(qui, 'src/aula3d.ts')],
  outfile: path.join(qui, '../aula3d.js'),
  bundle: true,
  minify: true,
  format: 'iife',
  target: 'es2020',
  nodePaths: [path.join(radice, 'scranno/node_modules')],
  legalComments: 'eof',
  banner: { js: '/* Scranno, Aula 3D. Motore da scranno/src/three, three.js 0.186.1 (MIT). Sorgente: 3d/src/aula3d.ts */' },
});
console.log('ok');
