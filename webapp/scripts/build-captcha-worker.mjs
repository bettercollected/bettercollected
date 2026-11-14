// Builds the Web Worker of the automatic spam check into public/captcha/worker-v1.js.
//
//   yarn build:captcha-worker            (writes the file)
//   node scripts/build-captcha-worker.mjs --stdout   (prints it: what the freshness test compares)
//
// The worker (src/utils/captcha/captcha-worker.ts) is committed as a static file, like the embed script
// (public/embed/v1.js): the bundler's own worker support does not bundle it (Turbopack serves the
// TypeScript file as a plain asset), and a static, same-origin file is also what a strict CSP and a
// framed form need. src/utils/captcha/captcha-worker-bundle.test.ts fails when the committed file is not
// what this script builds from the source, so the two cannot drift.
import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { build } from 'vite';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
export const OUTPUT = resolve(root, 'public/captcha/worker-v1.js');

const BANNER = '/* BetterCollected spam check worker v1: built from src/utils/captcha/captcha-worker.ts by scripts/build-captcha-worker.mjs; do not edit. Includes @noble/hashes (MIT). */\n';

/** The worker's code as the build makes it. */
export async function bundleWorker() {
    const result = await build({
        root,
        configFile: false,
        logLevel: 'silent',
        build: {
            write: false,
            minify: true,
            target: 'es2019',
            lib: { entry: resolve(root, 'src/utils/captcha/captcha-worker.ts'), formats: ['iife'], name: 'BcCaptchaWorker', fileName: () => 'worker-v1.js' }
        }
    });
    const outputs = Array.isArray(result) ? result : [result];
    const chunk = outputs[0].output.find((item) => item.type === 'chunk');
    return BANNER + chunk.code;
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
    const code = await bundleWorker();
    if (process.argv.includes('--stdout')) {
        process.stdout.write(code);
        process.exit(0);
    }
    mkdirSync(dirname(OUTPUT), { recursive: true });
    writeFileSync(OUTPUT, code);
    console.log(`wrote ${OUTPUT} (${code.length} bytes)`);
}
