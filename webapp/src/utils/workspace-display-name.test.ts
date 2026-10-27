import { describe, expect, it } from 'vitest';

import { looksLikeId, workspaceDisplayName } from './workspace-display-name';

const OBJECT_ID = '65f1c0a2b3d4e5f607182930';
const UUID = '3f2b8c1e-9a4d-4c7e-8b21-5d6f7a8b9c0d';

describe('workspaceDisplayName', () => {
    it('prefers the title', () => {
        expect(workspaceDisplayName({ title: ' Acme Health ', workspaceName: 'acme' })).toBe('Acme Health');
    });

    it('falls back to a readable handle', () => {
        expect(workspaceDisplayName({ title: '', workspaceName: 'acme-health' })).toBe('acme-health');
        expect(workspaceDisplayName({ title: undefined, workspaceName: 'acme' })).toBe('acme');
    });

    it('never returns an id: an object id, a UUID, or the workspace own ids', () => {
        expect(workspaceDisplayName({ title: '', workspaceName: OBJECT_ID })).toBeUndefined();
        expect(workspaceDisplayName({ title: '  ', workspaceName: UUID })).toBeUndefined();
        expect(workspaceDisplayName({ title: '', workspaceName: 'owner-1', ownerId: 'owner-1' })).toBeUndefined();
        expect(workspaceDisplayName({ title: '', workspaceName: 'ws-1', id: 'ws-1' })).toBeUndefined();
    });

    it('has no name for a missing workspace', () => {
        expect(workspaceDisplayName(undefined)).toBeUndefined();
        expect(workspaceDisplayName({})).toBeUndefined();
    });

    it('keeps a title even when it looks like an id', () => {
        expect(workspaceDisplayName({ title: OBJECT_ID, workspaceName: 'acme' })).toBe(OBJECT_ID);
    });
});

describe('looksLikeId', () => {
    it('recognises object ids and UUIDs, not words', () => {
        expect(looksLikeId(OBJECT_ID)).toBe(true);
        expect(looksLikeId(UUID.toUpperCase())).toBe(true);
        expect(looksLikeId('acme')).toBe(false);
        expect(looksLikeId('deadbeef')).toBe(false);
    });
});
