import { describe, expect, it } from 'vitest';

import { portalBase, portalPath, portalSegment } from './portal-path';

const ORIGIN = 'https://forms.example';
/** A path stays on this site: one leading "/", then not "/" or "\" (no protocol-relative URL). */
const staysOnSite = (path: string) => {
    expect(path).toMatch(/^\/(?![/\\])/);
    expect(new URL(path, ORIGIN).origin).toBe(ORIGIN);
};

const HOSTILE = ['/', '//evil.com', '/evil.com', '%2Fevil.com', '%2F%2Fevil.com', '%2F', 'javascript:alert(1)', '\\\\evil.com', '../../x', 'a/b', '', ' '];

describe('portal paths', () => {
    it('builds the usual paths', () => {
        expect(portalPath('acme', false, 'forms')).toBe('/acme/forms');
        expect(portalPath('acme', false, 'submissions', 'r1', 'form')).toBe('/acme/submissions/r1/form');
        expect(portalPath('acme', true, 'forms', 'intake')).toBe('/forms/intake');
        expect(portalBase('acme', false)).toBe('/acme');
        expect(portalBase('acme', true)).toBe('');
    });

    it.each(HOSTILE)('never leaves the site for the workspace handle %j', (handle) => {
        staysOnSite(portalPath(handle, false, 'my-submissions'));
        staysOnSite(portalPath(handle, false, 'submissions', 'uuid', 'X1', 'form'));
        staysOnSite(`${portalBase(handle, false)}/forms`);
    });

    it.each(HOSTILE)('keeps %j inside one segment as a slug, id or typed number', (value) => {
        for (const path of [portalPath('acme', false, 'forms', value), portalPath(null, true, 'submissions', 'uuid', value, 'form')]) {
            staysOnSite(path);
            expect(new URL(path, ORIGIN).pathname.startsWith(path.startsWith('/acme') ? '/acme/forms' : '/submissions/uuid')).toBe(true);
        }
    });

    it('encodes a value once, whether or not it arrives encoded', () => {
        expect(portalSegment('my workspace')).toBe('my%20workspace');
        expect(portalSegment('my%20workspace')).toBe('my%20workspace');
        expect(portalSegment('%2Fevil.com')).toBe('%2Fevil.com');
        expect(portalSegment('100%')).toBe('100%25');
    });
});
