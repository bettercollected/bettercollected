// What an automation card says: the chip, the one-line summary pieces and the
// failed-delivery count. Pure logic, no rendering.
import { describe, expect, it } from 'vitest';

import { chipFor, failedCount, listStats, shortList } from './summary';

describe('chipFor', () => {
    it('says "not set up" when nothing is configured, whatever else is known', () => {
        expect(chipFor({ configured: false, on: false })).toEqual({ kind: 'not-set-up' });
        expect(chipFor({ configured: false, on: true, failed: 3 })).toEqual({ kind: 'not-set-up' });
    });

    it('says On or Off for a configured automation', () => {
        expect(chipFor({ configured: true, on: true })).toEqual({ kind: 'on' });
        expect(chipFor({ configured: true, on: false })).toEqual({ kind: 'off' });
        expect(chipFor({ configured: true, on: true, failed: 0 })).toEqual({ kind: 'on' });
    });

    it('puts deliveries that did not go out before On and Off, with the count', () => {
        expect(chipFor({ configured: true, on: true, failed: 2 })).toEqual({ kind: 'not-sent', count: 2 });
        expect(chipFor({ configured: true, on: false, failed: 1 })).toEqual({ kind: 'not-sent', count: 1 });
    });

    it('asks for a reconnect before anything else', () => {
        expect(chipFor({ configured: true, on: true, reconnect: true, failed: 4 })).toEqual({ kind: 'reconnect' });
    });

    it('says when this server cannot send (no mail server), after failures', () => {
        expect(chipFor({ configured: true, on: true, unavailable: true })).toEqual({ kind: 'unavailable' });
        expect(chipFor({ configured: true, on: true, unavailable: true, failed: 2 })).toEqual({ kind: 'not-sent', count: 2 });
    });
});

describe('listStats', () => {
    const hooks = [
        { host: 'hooks.example', enabled: true },
        { host: 'crm.example', enabled: true },
        { host: 'old.example', enabled: false }
    ];

    it('counts the entries that are on and keeps their names in list order', () => {
        expect(
            listStats(
                hooks,
                (h) => h.enabled,
                (h) => h.host
            )
        ).toEqual({ total: 3, on: 2, labels: ['hooks.example', 'crm.example'] });
    });

    it('is empty for no list', () => {
        expect(
            listStats(
                undefined,
                () => true,
                () => 'x'
            )
        ).toEqual({ total: 0, on: 0, labels: [] });
    });

    it('leaves out entries without a name', () => {
        expect(
            listStats(
                [{ n: undefined }, { n: 'a' }],
                () => true,
                (i) => i.n
            )
        ).toEqual({ total: 2, on: 2, labels: ['a'] });
    });
});

describe('shortList', () => {
    it('shows up to two names and counts the rest', () => {
        expect(shortList([])).toBe('');
        expect(shortList(['a.example'])).toBe('a.example');
        expect(shortList(['a.example', 'b.example'])).toBe('a.example, b.example');
        expect(shortList(['a.example', 'b.example', 'c.example', 'd.example'])).toBe('a.example, b.example +2');
    });
});

describe('failedCount', () => {
    it('is the total of the failed page', () => {
        expect(failedCount({ total: 3 }, undefined)).toBe(3);
        expect(failedCount({ total: 0 }, undefined)).toBe(0);
    });

    it('is unknown while loading and when the member may not read the log', () => {
        expect(failedCount(undefined, undefined)).toBeUndefined();
        expect(failedCount(undefined, { status: 403 })).toBeUndefined();
        expect(failedCount({ total: 5 }, { status: 403 })).toBeUndefined();
    });
});
