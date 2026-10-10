// Empacota a prévia (Remotion Player + composição) para a interface web: server/web/player.js (+ player.css)
import {build} from 'esbuild';
await build({
  entryPoints: ['src/player.tsx'], bundle: true, minify: true, format: 'iife', globalName: 'KLZPlayer',
  outfile: '../server/web/player.js', target: ['es2020'], jsx: 'automatic', logLevel: 'info',
  loader: {'.woff2': 'dataurl', '.woff': 'dataurl'}, define: {'process.env.NODE_ENV': '"production"'},
});
