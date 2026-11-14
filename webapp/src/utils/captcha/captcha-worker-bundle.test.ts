// The Web Worker is committed as a static file (public/captcha/worker-v1.js): it must be what
// `yarn build:captcha-worker` builds from the source, and it must answer as the TypeScript solver does.
// @vitest-environment node
import { readFileSync } from 'fs';
import { resolve } from 'path';

import { execFileSync } from 'child_process';
import { describe, expect, it } from 'vitest';
import vm from 'vm';

import { Solver } from './solver-core';

const ROOT = resolve(__dirname, '../../..');
const FILE = resolve(__dirname, '../../../public/captcha/worker-v1.js');
const CHALLENGE = 'eyJ2IjoxfQ.c2lnbmF0dXJl';

describe('the spam check worker file', () => {
    it('is what the build makes from the source (run `yarn build:captcha-worker` after changing it)', () => {
        const built = execFileSync(process.execPath, ['scripts/build-captcha-worker.mjs', '--stdout'], { cwd: ROOT, encoding: 'utf8', maxBuffer: 10_000_000 });
        expect(readFileSync(FILE, 'utf8')).toBe(built);
    }, 60_000);

    it('answers a challenge with the counters the solver finds, makes no request and keeps nothing', () => {
        const sent: unknown[] = [];
        const scope: any = { postMessage: (message: unknown) => sent.push(message) };
        const sandbox = { self: scope, performance, TextEncoder, Uint8Array, Uint32Array, ArrayBuffer, DataView, Math, Number, String, Array, Error };
        vm.runInNewContext(readFileSync(FILE, 'utf8'), sandbox);
        scope.onmessage({ data: { challenge: CHALLENGE, bits: 14, subpuzzles: 8 } });
        const solver = new Solver(CHALLENGE, 14);
        solver.step(Infinity);
        expect(sent).toEqual([{ counters: solver.counters }]);
        // nothing that reaches the network or the device is even in the worker's scope
        expect(readFileSync(FILE, 'utf8')).not.toMatch(/fetch\(|XMLHttpRequest|localStorage|indexedDB|importScripts|WebSocket/);
    });

    it('is a classic script a Worker can start without a bundler', () => {
        expect(readFileSync(FILE, 'utf8')).not.toMatch(/^\s*(import|export)\s/m);
    });
});
