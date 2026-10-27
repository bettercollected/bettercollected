// The locale files: English and Dutch carry the same keys, plurals use the
// i18next `_one` / `_other` keys (no "(s)"), and the Dutch dashboard speaks one
// register ("u").
import i18n from 'i18next';
import { describe, expect, it } from 'vitest';

import commonEn from '../public/locales/en/common.json';
import commonNl from '../public/locales/nl/common.json';
import builderEn from '../public/locales/en/builder.json';
import builderNl from '../public/locales/nl/builder.json';
import respondentEn from '../public/locales/en/respondent.json';
import respondentNl from '../public/locales/nl/respondent.json';

type Tree = { [key: string]: string | Tree };

const leaves = (tree: Tree, prefix = ''): Array<[string, string]> =>
    Object.entries(tree).flatMap(([key, value]) => (typeof value === 'string' ? [[`${prefix}${key}`, value] as [string, string]] : leaves(value, `${prefix}${key}.`)));

const namespaces = { common: [commonEn, commonNl], builder: [builderEn, builderNl], respondent: [respondentEn, respondentNl] } as const;

describe('locale files', () => {
    for (const [name, [en, nl]] of Object.entries(namespaces)) {
        it(`${name}: English and Dutch have the same keys`, () => {
            const enKeys = leaves(en as Tree).map(([key]) => key).sort();
            const nlKeys = leaves(nl as Tree).map(([key]) => key).sort();
            expect(nlKeys).toEqual(enKeys);
        });
    }

    it('has no "(s)"-style plurals in either language', () => {
        const offenders: string[] = [];
        for (const [en, nl] of Object.values(namespaces)) {
            for (const tree of [en, nl]) {
                for (const [key, value] of leaves(tree as Tree)) {
                    if (/\w\((s|en|n|e|es)\)|\(e\)l\(en\)/.test(value)) offenders.push(key);
                }
            }
        }
        expect(offenders).toEqual([]);
    });
});

describe('plural keys', () => {
    const instance = i18n.createInstance();
    instance.init({
        resources: { en: { common: commonEn }, nl: { common: commonNl } },
        lng: 'en',
        fallbackLng: 'en',
        ns: ['common'],
        defaultNS: 'common',
        interpolation: { escapeValue: false }
    });

    it('English: the forms count and the export note', () => {
        const en = instance.getFixedT('en');
        expect(en('FORMS_TOOLBAR.COUNT', { count: 1 })).toBe('1 form');
        expect(en('FORMS_TOOLBAR.COUNT', { count: 3 })).toBe('3 forms');
        expect(en('FORM_MENU.OPEN_FORMULIEREN_EXPORT_UNMAPPED', { count: 1 })).toContain('1 item was left out');
        expect(en('FORM_MENU.OPEN_FORMULIEREN_EXPORT_UNMAPPED', { count: 2 })).toContain('2 items were left out');
    });

    it('Dutch: the forms count and the export note', () => {
        const nl = instance.getFixedT('nl');
        expect(nl('FORMS_TOOLBAR.COUNT', { count: 1 })).toBe('1 formulier');
        expect(nl('FORMS_TOOLBAR.COUNT', { count: 3 })).toBe('3 formulieren');
        expect(nl('FORM_MENU.OPEN_FORMULIEREN_EXPORT_UNMAPPED', { count: 1 })).toContain('1 onderdeel is weggelaten');
        expect(nl('FORM_MENU.OPEN_FORMULIEREN_EXPORT_UNMAPPED', { count: 4 })).toContain('4 onderdelen zijn weggelaten');
    });
});

describe('the Dutch dashboard register', () => {
    // The dashboard (common + builder) addresses people with "u" / "uw". The
    // respondent namespace keeps its own "je". Inside common, the responder
    // portal sign-in text stays in the respondent's register, and the builder's
    // hint quotes what respondents will read.
    const RESPONDENT_FACING = new Set(['RESPONDER_SECTION.FEATURES_HEADING', 'RESPONDER_SECTION.FEATURE_2', 'RESPONDER_SECTION.FEATURE_3', 'SIGNIN_SCREEN.MODAL.DESCRIPTION', 'REGISTRATION.DIALOG.ORGANISATION_HINT']);
    const informal = /\b(je|jouw|jouwe|jij|jou|jezelf)\b/i;

    it('has no "je" / "jouw" outside the respondent-facing strings', () => {
        const offenders = [...leaves(commonNl as Tree), ...leaves(builderNl as Tree)].filter(([key, value]) => !RESPONDENT_FACING.has(key) && informal.test(value.replace(/\{\{[^}]*\}\}/g, ''))).map(([key]) => key);
        expect(offenders).toEqual([]);
    });

    it('keeps "je" in the respondent namespace', () => {
        const withJe = leaves(respondentNl as Tree).filter(([, value]) => informal.test(value));
        expect(withJe.length).toBeGreaterThan(20);
    });

    it('capitalises the Open button of the form menu', () => {
        expect(commonNl.BUTTON.OPEN).toBe('Openen');
    });
});
