// MIT. Maintenance build only; the installed CLI needs Node, not esbuild/npm.
import { createHash } from 'node:crypto';
import { readFile, writeFile } from 'node:fs/promises';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

const root = fileURLToPath(new URL('../', import.meta.url));
const engine = path.join(root, 'src/visualsectors_toolkit/context_engine');
const manifest = JSON.parse(await readFile(path.join(engine, 'manifest.json'), 'utf8'));
for (const [name, expected] of Object.entries(manifest.source_sha256)) {
  const source = await readFile(path.join(engine, 'source', name));
  if (createHash('sha256').update(source).digest('hex') !== expected) {
    throw new Error(`Released source hash differs: ${name}; review and version the port, do not silently rebuild.`);
  }
}
const args = process.argv.slice(2);
if (args.length !== 0 && (args.length !== 2 || args[0] !== '--esbuild')) {
  throw new Error('Usage: node scripts/build-context-engine.mjs [--esbuild PATH_TO_ESBUILD_MAIN_JS]');
}
const { build, version } = await import(args.length ? pathToFileURL(path.resolve(args[1])).href : 'esbuild');
if (version !== manifest.build_esbuild_version) throw new Error(`Use reviewed esbuild ${manifest.build_esbuild_version}.`);
const result = await build({
  absWorkingDir: root,
  entryPoints: ['src/visualsectors_toolkit/context_engine/source/entry.ts'],
  outfile: path.join(engine, 'engine.mjs'),
  bundle: true, platform: 'node', format: 'esm', target: 'node22',
  charset: 'utf8', legalComments: 'inline', sourcemap: false,
  write: false,
  banner: { js: '// MIT — Copyright 2026 Visual Sectors. Ported from vs-intelligence 863489f, preset-skills 0.5.0.\n// Generated with scripts/build-context-engine.mjs; inspect the adjacent source/ files.' },
});
const output = result.outputFiles[0];
if (!output || createHash('sha256').update(output.contents).digest('hex') !== manifest.engine_sha256) {
  throw new Error('Generated engine differs from its reviewed hash; no runtime was overwritten.');
}
await writeFile(path.join(engine, 'engine.mjs'), output.contents);
console.log('Built the pinned screener context engine; no network or data retrieval.');
