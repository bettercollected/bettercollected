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

describe('Dutch action labels', () => {
    // Menu items and buttons are infinitives with the object first, like
    // "Openen", "Bewerken" and "Link kopiëren": "Formulier vastzetten", not
    // "Vastzetten formulier" and not the imperative "Maak QR-code".
    const actions = (): Array<[string, string]> => [
        ...leaves(commonNl.FORM_MENU as Tree, 'FORM_MENU.'),
        ['FORM_PAGE.EDIT_FORM', commonNl.FORM_PAGE.EDIT_FORM],
        ['FORM_PAGE.SHARE_FORM', commonNl.FORM_PAGE.SHARE_FORM],
        ['BUTTON.CUSTOMIZE_LINK', commonNl.BUTTON.CUSTOMIZE_LINK],
        ...leaves(builderNl.OPEN_FORMULIEREN_IMPORT.PUBLISH_BLOCKED as Tree, 'PUBLISH_BLOCKED.').filter(([key]) => /OPEN_REPORT|MARK_REVIEWED/.test(key)),
        ['REPORT.OPEN_EDITOR', builderNl.OPEN_FORMULIEREN_IMPORT.REPORT.OPEN_EDITOR],
        ['REPORT.MARK_REVIEWED', builderNl.OPEN_FORMULIEREN_IMPORT.REPORT.MARK_REVIEWED],
        ['BANNER.LINK', builderNl.OPEN_FORMULIEREN_IMPORT.BANNER.LINK]
    ];
    const imperative = /^(Maak|Bewerk|Deel|Verwijder|Dupliceer|Open|Markeer|Kopieer|Bekijk|Download|Zet|Pas|Gebruik|Probeer)\b/;

    it('starts none of the form menu, the form toolbar or the import report buttons with an imperative', () => {
        // the notes that follow an export are sentences, not actions
        const offenders = actions()
            .filter(([key]) => !/EXPORT_(CLEAN|UNMAPPED|TOO_LARGE|ERROR)|DUPLICATE_ERROR/.test(key))
            .filter(([, value]) => imperative.test(value))
            .map(([key, value]) => `${key}: ${value}`);
        expect(offenders).toEqual([]);
    });

    it('has no imperative left in the common buttons, the builder tips and the retry and review buttons', () => {
        const checked: Array<[string, string]> = [
            ...leaves(commonNl.BUTTON as Tree, 'BUTTON.'),
            ['CREATE_FORM', commonNl.CREATE_FORM],
            ['FORM_PAGE.SETTINGS.DEFAULT.FORM_PURPOSE.SEE_DETAILS', commonNl.FORM_PAGE.SETTINGS.DEFAULT.FORM_PURPOSE.SEE_DETAILS],
            ...leaves(builderNl.TIPS.ACTIONS as Tree, 'TIPS.ACTIONS.'),
            ['REGISTRATION.TRY_AGAIN', builderNl.REGISTRATION.TRY_AGAIN],
            ['REPORT.MARK_REVIEW_AGAIN', builderNl.OPEN_FORMULIEREN_IMPORT.REPORT.MARK_REVIEW_AGAIN]
        ];
        const imperativeStart = /^(Maak|Bewerk|Deel|Verwijder|Dupliceer|Open|Markeer|Kopieer|Bekijk|Download|Zet|Pas|Gebruik|Probeer|Voeg|Selecteer|Sla|Sleep|Ga|Nodig|Vraag|Weer)\b/;
        // "Open Werkruimte" style: a capitalised noun after a verb is the sign of the old pattern
        const offenders = checked.filter(([, value]) => imperativeStart.test(value.trim())).map(([key, value]) => `${key}: ${value}`);
        expect(offenders).toEqual([]);
        expect(commonNl.BUTTON).toMatchObject({ ADD_FORM: 'Formulier toevoegen', CREATE_WORKSPACE: 'Werkruimte maken', OPEN_WORKSPACE: 'Werkruimte openen' });
        expect(commonNl.CREATE_FORM).toBe('Formulier maken');
        expect(builderNl.REGISTRATION.TRY_AGAIN).toBe('Opnieuw proberen');
        expect(builderNl.TIPS.ACTIONS).toMatchObject({ CTRL_D: 'Veld dupliceren', CTRL_DELETE: 'Veld verwijderen' });
    });

    it('puts the object first in the form menu', () => {
        expect(commonNl.FORM_MENU).toMatchObject({
            PIN_FORM: 'Formulier vastzetten',
            DUPLICATE_FORM: 'Formulier dupliceren',
            DELETE_FORM: 'Formulier verwijderen',
            GENERATE_QR: 'QR-code maken',
            MAKE_FORM_PRIVATE: 'Formulier privé maken',
            MAKE_FORM_PUBLIC: 'Formulier openbaar maken'
        });
        expect(commonNl.FORM_PAGE).toMatchObject({ EDIT_FORM: 'Formulier bewerken', SHARE_FORM: 'Formulier delen' });
    });

    it('words the import report buttons as infinitives', () => {
        const report = builderNl.OPEN_FORMULIEREN_IMPORT;
        expect(report.REPORT.OPEN_EDITOR).toBe('Openen in de editor');
        expect(report.REPORT.MARK_REVIEWED).toBe('Markeren als nagekeken');
        expect(report.PUBLISH_BLOCKED.MARK_REVIEWED).toBe('Markeren als nagekeken');
        expect(report.PUBLISH_BLOCKED.OPEN_REPORT).toBe('Importrapport openen');
    });
});

describe('Dutch field type labels in the registration answers list', () => {
    const types = (tree: Tree) => (tree as any).REGISTRATION.FORM.TYPE as Record<string, string>;

    it('names every type in Dutch, with no English type name left', () => {
        const nl = types(builderNl as Tree);
        const en = types(builderEn as Tree);
        expect(Object.keys(nl).sort()).toEqual(Object.keys(en).sort());
        // the same word in both languages is fine only for these
        const same = new Set(['matrix']);
        for (const [type, label] of Object.entries(nl)) {
            if (!same.has(type) && type !== 'url') expect(label, type).not.toBe(en[type]);
        }
        expect(nl.short_text).toBe('Korte tekst');
        expect(nl.multiple_choice).toBe('Meerkeuze');
        expect(nl.long_text).toBe('Lange tekst');
        expect(nl.hidden).toBe('Verborgen veld');
    });
});

describe('Dutch sentences for a variable that was not carried over', () => {
    const causes = Object.entries((builderNl.OPEN_FORMULIEREN_IMPORT as any).VARIABLE_CAUSE as Record<string, string>);

    it('calls a variable "deze variabele" and "hij", never "zij" or "haar"', () => {
        const offenders = causes.filter(([, value]) => /\b(zij|haar|ze)\b/i.test(value)).map(([key]) => key);
        expect(offenders).toEqual([]);
        expect((builderNl.OPEN_FORMULIEREN_IMPORT.REASON as any).user_variable_calculated).not.toMatch(/\bhaar\b/);
    });

    it('has no comma splice before "daarom" and no "vult" for a rule that sets a variable', () => {
        expect(causes.filter(([, value]) => /, daarom/.test(value)).map(([key]) => key)).toEqual([]);
        expect(causes.filter(([, value]) => /\bvult\b|\bgevuld\b/.test(value)).map(([key]) => key)).toEqual([]);
    });

    it('refers to a placeholder with "Dat", in a sentence of its own', () => {
        for (const [key, value] of causes.filter(([, value]) => value.includes('{{source}}') && /\bDat\b|\bDie\b/.test(value))) {
            expect(value, key).toMatch(/”\. (Dat|Die) /);
        }
        expect(causes.filter(([, value]) => /”, (dat|die)\b/.test(value)).map(([key]) => key)).toEqual([]);
    });

    it('is grammatical in the cases that were reviewed', () => {
        const dutch = Object.fromEntries(causes);
        expect(dutch.initial_value).toBe('Deze variabele bevat een deling en heeft een beginwaarde; daarom is hij niet overgenomen.');
        expect(dutch.too_many).toContain('Deze past er niet meer bij.');
        expect(dutch.source_conditional).toBe('Deze variabele gebruikt “{{source}}”. Dat kan door een regel verborgen worden; het bronformulier laat het dan leeg.');
        expect(dutch.rejected).toBe('De formuliereditor heeft deze berekening niet aangenomen.');
    });
});
