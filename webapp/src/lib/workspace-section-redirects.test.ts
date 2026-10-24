// The old addresses of the pages that became Single sign-on and AI tabs
// redirect permanently (next.config.js), so bookmarks, docs and links in
// mails keep working.
import path from 'path';

import { createRequire } from 'module';
import { describe, expect, it } from 'vitest';

import { workspaceSectionUrls } from './workspace-sections';

const require = createRequire(import.meta.url);
const nextConfig = require(path.resolve(__dirname, '../../next.config.js'));

describe('redirects from the old workspace pages', () => {
    const urls = workspaceSectionUrls(':workspace_name');

    it.each([
        ['ai-settings', urls.aiSettings],
        ['ai-profile', urls.aiProfile],
        ['ai-memory', urls.aiMemory],
        ['api-keys', urls.aiMcp],
        ['domains', urls.domains]
    ])('/dashboard/%s goes to %s, permanently', async (old, target) => {
        const redirects: Array<{ source: string; destination: string; permanent: boolean }> = await nextConfig.redirects();
        expect(redirects).toContainEqual({ source: `/:workspace_name/dashboard/${old}`, destination: target, permanent: true });
    });

    it('redirects nothing else', async () => {
        expect(await nextConfig.redirects()).toHaveLength(5);
    });
});
