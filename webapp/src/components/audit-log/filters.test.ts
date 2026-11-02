import { describe, expect, it } from 'vitest';

import { EMPTY_FILTERS, activeFilterCount, auditQuery, filtersToSearch, hidesBreakGlass, parseFilters } from './filters';

const parse = (search: string) => parseFilters(new URLSearchParams(search));

describe('the filters in the address', () => {
    it('reads areas, person, form and days, and writes them back the same', () => {
        const search = 'area=access&area=responses&who=u_1&about=1&form=f_1&from=2026-10-01&to=2026-10-31';
        const filters = parse(search);
        expect(filters).toEqual({ areas: ['access', 'responses'], who: 'u_1', about: true, form: 'f_1', from: '2026-10-01', to: '2026-10-31' });
        expect(parse(filtersToSearch(filters))).toEqual(filters);
    });

    it('writes nothing for no filters', () => {
        expect(filtersToSearch(EMPTY_FILTERS)).toBe('');
        expect(parse('')).toEqual({ areas: [], who: undefined, about: false, form: undefined, from: undefined, to: undefined });
    });

    it('drops what the server would refuse: unknown areas, ids with odd characters, impossible days', () => {
        expect(parse('area=everything&area=forms&who=a%20b&form=../x&from=2026-13-40&to=yesterday')).toEqual({ areas: ['forms'], who: undefined, about: false, form: undefined, from: undefined, to: undefined });
    });

    it('keeps "also what was done to them" only with a person', () => {
        expect(parse('about=1').about).toBe(false);
        expect(filtersToSearch({ areas: [], about: true })).toBe('');
    });

    it('counts the filters set, not the hidden default', () => {
        expect(activeFilterCount(EMPTY_FILTERS, true)).toBe(0);
        expect(activeFilterCount(parse('area=access&area=forms&who=u&form=f&from=2026-10-01'), true)).toBe(5);
        expect(activeFilterCount(parse('form=f'), false)).toBe(0);
    });
});

describe('the request for a page', () => {
    const params = (query: string) => new URLSearchParams(query);

    it('hides the break-glass requests by default: the other areas plus the rare security kinds', () => {
        const query = params(auditQuery(EMPTY_FILTERS, { limit: 20 }));
        expect(query.getAll('area')).toEqual(['access', 'members', 'forms', 'responses', 'api_keys']);
        expect(query.getAll('event')).toEqual(['sso_break_glass_sign_in', 'totp_policy_changed', 'totp_reset']);
        expect(query.getAll('event')).not.toContain('sso_break_glass_request');
        expect(query.get('limit')).toBe('20');
        expect(hidesBreakGlass(EMPTY_FILTERS)).toBe(true);
    });

    it('asks for exactly the chosen areas, and shows the break-glass requests when Security is chosen', () => {
        const filters = parse('area=security');
        const query = params(auditQuery(filters));
        expect(query.getAll('area')).toEqual(['security']);
        expect(query.getAll('event')).toEqual([]);
        expect(hidesBreakGlass(filters)).toBe(false);
        // another area alone still hides them
        expect(hidesBreakGlass(parse('area=access'))).toBe(true);
    });

    it('sends the person as actor, or as involving, and the form only for the workspace route', () => {
        expect(params(auditQuery(parse('who=u_1'))).get('actor')).toBe('u_1');
        const about = params(auditQuery(parse('who=u_1&about=1'), {}, 'f_1'));
        expect(about.get('involving')).toBe('u_1');
        expect(about.get('actor')).toBeNull();
        expect(about.get('form_id')).toBe('f_1');
        expect(params(auditQuery(parse('who=u_1'))).get('form_id')).toBeNull();
    });

    it('turns days into inclusive UTC boundaries and carries the cursor', () => {
        const query = params(auditQuery(parse('from=2026-10-01&to=2026-10-31'), { cursor: 'abc' }));
        expect(query.get('from')).toBe('2026-10-01T00:00:00Z');
        expect(query.get('to')).toBe('2026-10-31T23:59:59.999Z');
        expect(query.get('cursor')).toBe('abc');
    });
});
