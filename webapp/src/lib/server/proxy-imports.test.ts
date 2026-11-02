import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

// src/proxy.ts runs in front of every page. What it imports (and what those import, inside the app) must not
// reach next/headers, the API helpers or React: a load-time failure there would take every page down. This
// walks the proxy's import graph in the source.
const SRC = resolve(__dirname, '../..');
const FORBIDDEN = [/from 'next\/headers'/, /from 'react'/, /@app\/lib\/server\/api'/, /@app\/lib\/server\/custom-domain'/, /'server-only'/];

function local(file: string): string[] {
    const text = readFileSync(file, 'utf8');
    const found: string[] = [];
    for (const match of text.matchAll(/from '(@app\/[^']+|\.{1,2}\/[^']+)'/g)) {
        const target = match[1].startsWith('@app/') ? resolve(SRC, match[1].slice(5)) : resolve(dirname(file), match[1]);
        for (const candidate of [`${target}.ts`, `${target}.tsx`, `${target}/index.ts`]) {
            try {
                readFileSync(candidate);
                found.push(candidate);
                break;
            } catch {
                /* try the next */
            }
        }
    }
    return found;
}

function graph(entry: string): string[] {
    const seen = new Set<string>();
    const queue = [entry];
    while (queue.length) {
        const file = queue.pop() as string;
        if (seen.has(file)) continue;
        seen.add(file);
        queue.push(...local(file));
    }
    return [...seen];
}

describe("the proxy's imports", () => {
    it('reach no server-only module of the app', () => {
        const files = graph(resolve(SRC, 'proxy.ts'));
        expect(files.map((file) => file.replace(`${SRC}/`, ''))).toEqual(expect.arrayContaining(['proxy.ts', 'lib/server/custom-domain-assertion.ts', 'lib/server/embed-policy.ts', 'lib/frame-ancestors.ts']));
        for (const file of files) {
            const text = readFileSync(file, 'utf8');
            for (const pattern of FORBIDDEN) expect(pattern.test(text), `${file} matches ${pattern}`).toBe(false);
        }
    });
});
