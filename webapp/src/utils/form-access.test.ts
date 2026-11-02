import i18n from 'i18next';
import { describe, expect, it } from 'vitest';

import enCommon from '../../public/locales/en/common.json';
import nlCommon from '../../public/locales/nl/common.json';
import { FORM_ACCESS_ERROR_CODES, exportFlagApplies, formAccessErrorKey, grantableRoles } from './form-access';

const EDITOR = ['form.read', 'form.edit', 'form.share', 'form.delete', 'response.read', 'response.annotate', 'response.export', 'response.delete', 'response.edit', 'analytics.read'];
const REVIEWER = ['form.read', 'response.read', 'response.annotate', 'analytics.read'];

describe('grantableRoles', () => {
    it('offers every role to someone who holds all of an Editor grant (a workspace Editor, Admin or Owner)', () => {
        expect(grantableRoles(EDITOR)).toEqual(['EDITOR', 'REVIEWER', 'VIEWER']);
    });

    it('never offers a role above the giver: no export means no Editor role', () => {
        expect(grantableRoles(EDITOR.filter((permission) => permission !== 'response.export'))).toEqual(['REVIEWER', 'VIEWER']);
    });

    it('offers the lower roles to someone who holds a Reviewer role on the form, and nothing to someone with no permissions', () => {
        expect(grantableRoles(REVIEWER)).toEqual(['REVIEWER', 'VIEWER']);
        expect(grantableRoles(['form.read', 'response.read', 'analytics.read'])).toEqual(['VIEWER']);
        expect(grantableRoles([])).toEqual([]);
        expect(grantableRoles(undefined)).toEqual([]);
    });
});

describe('formAccessErrorKey', () => {
    it('names the server code when it is one of ours', () => {
        for (const code of FORM_ACCESS_ERROR_CODES) expect(formAccessErrorKey({ status: 403, data: { code, message: 'x' } })).toBe(`STAFF.FORM_ACCESS.ERROR.${code}`);
    });

    it('falls back to the status, then to a plain failure, and never to the server text', () => {
        expect(formAccessErrorKey({ status: 404, data: 'Not found' })).toBe('STAFF.FORM_ACCESS.ERROR.not_found');
        expect(formAccessErrorKey({ status: 403, data: { code: 'something_new' } })).toBe('STAFF.FORM_ACCESS.ERROR.forbidden');
        expect(formAccessErrorKey({ status: 500 })).toBe('STAFF.FORM_ACCESS.ERROR.generic');
        expect(formAccessErrorKey(undefined)).toBe('STAFF.FORM_ACCESS.ERROR.generic');
    });

    it('every code and fallback has a sentence in both languages', () => {
        const keys = [...FORM_ACCESS_ERROR_CODES, 'not_found', 'forbidden', 'generic'];
        for (const [name, common] of [['en', enCommon], ['nl', nlCommon]] as const) {
            const errors = (common as any).STAFF.FORM_ACCESS.ERROR;
            for (const key of keys) expect(typeof errors[key], `${name}: ${key}`).toBe('string');
        }
    });
});

describe('exportFlagApplies', () => {
    it('is false for an Editor grant, which exports anyway', () => {
        expect(exportFlagApplies('EDITOR')).toBe(false);
        expect(exportFlagApplies('REVIEWER')).toBe(true);
        expect(exportFlagApplies('VIEWER')).toBe(true);
    });
});

describe('the Teams plural keys', () => {
    const instance = i18n.createInstance();
    instance.init({ resources: { en: { common: enCommon }, nl: { common: nlCommon } }, lng: 'en', fallbackLng: 'en', ns: ['common'], defaultNS: 'common', interpolation: { escapeValue: false } });

    it('reads right for none, one and many, in both languages', () => {
        const en = instance.getFixedT('en');
        const nl = instance.getFixedT('nl');
        expect(en('STAFF.TEAMS.PEOPLE', { count: 1 })).toBe('1 person');
        expect(en('STAFF.TEAMS.PEOPLE', { count: 4 })).toBe('4 people');
        expect(nl('STAFF.TEAMS.PEOPLE', { count: 4 })).toBe('4 mensen');
        expect(en('STAFF.TEAMS.DELETE_BODY', { count: 0 })).toBe('It is not used on any form.');
        expect(en('STAFF.TEAMS.DELETE_BODY', { count: 1 })).toContain('1 form;');
        expect(nl('STAFF.TEAMS.DELETE_BODY', { count: 3 })).toContain('3 formulieren');
    });
});
