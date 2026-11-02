// The ?panel= value of an Automations side sheet: a fixed allow-list, nothing
// else becomes a panel.
import { describe, expect, it } from 'vitest';

import { panelName, parsePanel, withPanel } from './panels';

describe('parsePanel', () => {
    it('knows the six built-in panels', () => {
        expect(parsePanel('webhooks')).toEqual({ kind: 'webhooks', view: 'manage' });
        expect(parsePanel('webhooks-deliveries')).toEqual({ kind: 'webhooks', view: 'deliveries' });
        expect(parsePanel('email')).toEqual({ kind: 'email', view: 'manage' });
        expect(parsePanel('email-deliveries')).toEqual({ kind: 'email', view: 'deliveries' });
        expect(parsePanel('case-system')).toEqual({ kind: 'case-system', view: 'manage' });
        expect(parsePanel('case-system-deliveries')).toEqual({ kind: 'case-system', view: 'deliveries' });
    });

    it('knows an integration action by its id', () => {
        expect(parsePanel('action-3f2c9a1e-7b1d-4c2a-9d55-0a1b2c3d4e5f')).toEqual({ kind: 'action', actionId: '3f2c9a1e-7b1d-4c2a-9d55-0a1b2c3d4e5f', view: 'manage' });
    });

    it('treats everything else as no panel', () => {
        for (const value of [null, undefined, '', 'Webhooks', 'webhooks ', 'webhooks-deliveries-x', 'sheets', 'action-', 'action-a/b', 'action-a b', 'action-<img>', `action-${'a'.repeat(65)}`, '__proto__', 'constructor', 'toString', 'hasOwnProperty']) {
            expect(parsePanel(value)).toBeNull();
        }
    });

    it('does not offer a deliveries view for an integration action', () => {
        expect(parsePanel('action-abc-deliveries')).toEqual({ kind: 'action', actionId: 'abc-deliveries', view: 'manage' });
    });
});

describe('panelName', () => {
    it('is the inverse of parsePanel', () => {
        for (const name of ['webhooks', 'webhooks-deliveries', 'email', 'email-deliveries', 'case-system', 'case-system-deliveries', 'action-abc123']) {
            expect(panelName(parsePanel(name)!)).toBe(name);
        }
    });
});

describe('withPanel', () => {
    it('sets the panel and keeps the other parameters', () => {
        expect(withPanel('', { kind: 'webhooks', view: 'manage' })).toBe('?panel=webhooks');
        expect(withPanel('lang=nl', { kind: 'email', view: 'deliveries' })).toBe('?lang=nl&panel=email-deliveries');
        expect(withPanel('panel=email&lang=nl', { kind: 'webhooks', view: 'manage' })).toBe('?panel=webhooks&lang=nl');
    });

    it('removes the panel, and the whole query when nothing else is left', () => {
        expect(withPanel('panel=webhooks', null)).toBe('');
        expect(withPanel('panel=webhooks&lang=nl', null)).toBe('?lang=nl');
    });
});
