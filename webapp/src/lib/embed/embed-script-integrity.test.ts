import { createHash } from 'node:crypto';
import { readFileSync, readdirSync } from 'node:fs';
import { createRequire } from 'node:module';
import { resolve } from 'node:path';

import { describe, expect, it } from 'vitest';

import { embedSnippet } from '@app/utils/form-embed';

import { CURRENT_EMBED_SCRIPT, EMBED_SCRIPTS } from './embed-script';

const PUBLIC = resolve(__dirname, '../../../public');
const sha384 = (file: string) => `sha384-${createHash('sha384').update(readFileSync(file)).digest('base64')}`;

describe('the embed script files', () => {
    it('are exactly the registered ones, and none of them has changed since it was registered', () => {
        const registered = Object.values(EMBED_SCRIPTS);
        expect(readdirSync(resolve(PUBLIC, 'embed')).sort()).toEqual(registered.map((entry) => entry.path.replace('/embed/', '')).sort());
        for (const entry of registered) expect(sha384(resolve(PUBLIC, entry.path.slice(1)))).toBe(entry.integrity);
    });

    it('are the ones the snippet names, with the hash of the file', () => {
        const snippet = embedSnippet('https://forms.example.org/acme/forms/contact', 'Contact form');
        expect(snippet).toContain(`src="https://forms.example.org${CURRENT_EMBED_SCRIPT.path}"`);
        expect(snippet).toContain(`integrity="${sha384(resolve(PUBLIC, CURRENT_EMBED_SCRIPT.path.slice(1)))}"`);
        expect(snippet).toContain('crossorigin="anonymous"');
    });

    it('are served immutable and readable by any site, and /embed.js is the current version', async () => {
        const config = createRequire(__filename)('../../../next.config.js');
        const headers: Array<{ source: string; headers: Array<{ key: string; value: string }> }> = await config.headers();
        const rule = headers.find((item) => item.source === '/embed/:path*');
        expect(rule?.headers).toEqual(expect.arrayContaining([
            { key: 'Access-Control-Allow-Origin', value: '*' },
            { key: 'Cache-Control', value: 'public, max-age=31536000, immutable' }
        ]));
        const alias = headers.find((item) => item.source === '/embed.js');
        expect(alias?.headers).toEqual(expect.arrayContaining([{ key: 'Access-Control-Allow-Origin', value: '*' }]));
        expect(alias?.headers.find((header) => header.key === 'Cache-Control')?.value).not.toMatch(/immutable/);
        const rewrites = await config.rewrites();
        expect(rewrites).toEqual(expect.arrayContaining([{ source: '/embed.js', destination: CURRENT_EMBED_SCRIPT.path }]));
    });
});
