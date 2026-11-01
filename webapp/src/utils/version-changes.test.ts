import i18n from 'i18next';
import { describe, expect, it } from 'vitest';

import type { VersionChange } from '@app/store/workspaces/form-versions-api';

import builderEn from '../../public/locales/en/builder.json';
import commonEn from '../../public/locales/en/common.json';
import builderNl from '../../public/locales/nl/builder.json';
import commonNl from '../../public/locales/nl/common.json';
import { describeChange, groupChanges } from './version-changes';

const instance = i18n.createInstance();
instance.init({
    resources: { en: { common: commonEn, builder: builderEn }, nl: { common: commonNl, builder: builderNl } },
    lng: 'en',
    fallbackLng: 'en',
    ns: ['common', 'builder'],
    defaultNS: 'common',
    interpolation: { escapeValue: false }
});
const en = instance.getFixedT('en') as any;
const nl = instance.getFixedT('nl') as any;

const change = (kind: string, scope: VersionChange['scope'], title: string | null, params: Record<string, any> = {}, ref = 'q1'): VersionChange => ({ kind, scope, ref, title, params });

const CASES: Array<[VersionChange, string, string]> = [
    [change('form_title_changed', 'form', null, { before: 'Old', after: 'New' }), 'The form title changed from “Old” to “New”.', 'De titel van het formulier is gewijzigd van “Old” in “New”.'],
    [change('language_changed', 'form', null, { before: 'en', after: 'nl' }), 'The form language changed from EN to NL.', 'De taal van het formulier is gewijzigd van EN in NL.'],
    [change('hidden_fields_added', 'form', null, { names: ['utm', 'ref'] }), 'Hidden fields added: utm, ref.', 'Verborgen velden toegevoegd: utm, ref.'],
    [change('page_added', 'page', null, { number: 3 }, 'p3'), 'Page 3 was added.', 'Pagina 3 is toegevoegd.'],
    [change('page_added', 'page', 'Contact', { number: 3 }, 'p3'), 'Page 3 (“Contact”) was added.', 'Pagina 3 (“Contact”) is toegevoegd.'],
    [change('page_moved', 'page', null, { before: 1, after: 2 }, 'p1'), 'Page 2 moved from position 1 to position 2.', 'Pagina 2 is verplaatst van positie 1 naar positie 2.'],
    [change('question_added', 'question', 'Email', { type: 'email', page: 2 }), '“Email” (Email) was added on page 2.', '“Email” (E-mailadres) is toegevoegd op pagina 2.'],
    [change('question_removed', 'question', 'Phone', { type: 'phone_number' }), '“Phone” (Phone number) was removed.', '“Phone” (Telefoonnummer) is verwijderd.'],
    [change('question_moved', 'question', 'Name', { before: 1, after: 2 }), '“Name” moved from page 1 to page 2.', '“Name” is verplaatst van pagina 1 naar pagina 2.'],
    [change('title_changed', 'question', 'Full name', { before: 'Name', after: 'Full name' }), 'The question “Name” was renamed “Full name”.', 'De vraag “Name” heet nu “Full name”.'],
    [change('type_changed', 'question', 'Age', { before: 'short_text', after: 'number' }), '“Age” changed from Short text to Number.', '“Age” is gewijzigd van Korte tekst in Getal.'],
    [change('required_changed', 'question', 'Age', { required: true }), '“Age” is now required.', '“Age” is nu verplicht.'],
    [change('required_changed', 'question', 'Age', { required: false }), '“Age” is no longer required.', '“Age” is niet meer verplicht.'],
    [change('choice_added', 'question', 'Colour', { value: 'Pink' }), '“Colour”: the option “Pink” was added.', '“Colour”: de optie “Pink” is toegevoegd.'],
    [change('choice_renamed', 'question', 'Colour', { before: 'Red', after: 'Crimson' }), '“Colour”: the option “Red” was renamed “Crimson”.', '“Colour”: de optie “Red” heet nu “Crimson”.'],
    [change('rules_changed', 'question', 'Colour', { added: 1, removed: 0, changed: 2 }), 'The rules of “Colour” changed: 1 added, 2 changed.', 'De regels van “Colour” zijn gewijzigd: 1 toegevoegd, 2 gewijzigd.'],
    [change('calculation_changed', 'question', 'Total'), 'The calculation of “Total” changed.', 'De berekening van “Total” is gewijzigd.'],
    [
        change('validation_changed', 'question', 'Name', { keys: ['maxLength', 'pattern'] }),
        'The limits on the answer to “Name” changed (maximum length, answer pattern).',
        'De grenzen voor het antwoord op “Name” zijn gewijzigd (maximale lengte, antwoordpatroon).'
    ],
    [change('other_changed', 'question', 'Name', { keys: ['placeholder', 'unknownKey'] }), '“Name”: something else changed (placeholder, unknownKey).', '“Name”: er is iets anders gewijzigd (plaatshouder, unknownKey).'],
    [change('other_changed', 'form', null, { keys: ['logo'] }, ''), 'Something else about the form changed (logo).', 'Er is iets anders aan het formulier gewijzigd (logo).'],
    [change('title_changed', 'question', '', { before: '', after: 'Name' }), 'The question “A question without a title” was renamed “Name”.', 'De vraag “Een vraag zonder titel” heet nu “Name”.']
];

describe('describeChange', () => {
    it.each(CASES)('words %j in English and Dutch', (entry, english, dutch) => {
        expect(describeChange(en, entry)).toBe(english);
        expect(describeChange(nl, entry)).toBe(dutch);
    });

    it('has a sentence in both languages for every kind the server sends', () => {
        const kinds = [
            'form_title_changed',
            'form_description_changed',
            'language_changed',
            'theme_changed',
            'welcome_page_changed',
            'ending_changed',
            'logo_settings_changed',
            'hidden_fields_added',
            'hidden_fields_removed',
            'page_added',
            'page_removed',
            'page_moved',
            'page_jumps_changed',
            'page_changed',
            'question_added',
            'question_removed',
            'question_moved',
            'title_changed',
            'type_changed',
            'required_changed',
            'choice_added',
            'choice_removed',
            'choice_renamed',
            'choice_logic_changed',
            'choices_reordered',
            'rules_changed',
            'rules_reordered',
            'logic_changed',
            'calculation_changed',
            'validation_changed',
            'description_changed',
            'other_changed'
        ];
        for (const kind of kinds) {
            for (const t of [en, nl]) {
                const text = describeChange(
                    t,
                    change(
                        kind,
                        kind.startsWith('page')
                            ? 'page'
                            : kind.startsWith('form') || ['language_changed', 'theme_changed', 'welcome_page_changed', 'ending_changed', 'logo_settings_changed', 'hidden_fields_added', 'hidden_fields_removed'].includes(kind)
                              ? 'form'
                              : 'question',
                        'T',
                        { type: 'short_text', number: 1, before: 1, after: 2, required: true, keys: ['placeholder'], names: ['a'], value: 'v', added: 1, removed: 1, changed: 1, page: 1 }
                    )
                );
                expect(text, kind).not.toBe(kind);
                expect(text, kind).not.toMatch(/FORM_VERSIONS|\{\{/);
            }
        }
    });

    it('names the question types the builder does not list, and shows an unknown one as it is', () => {
        const added = (type: string) => change('question_added', 'question', 'Sign', { type, page: 1 });
        expect(describeChange(en, added('signature'))).toBe('\u201CSign\u201D (Signature) was added on page 1.');
        expect(describeChange(nl, added('signature'))).toBe('\u201CSign\u201D (Handtekening) is toegevoegd op pagina 1.');
        expect(describeChange(en, added('brand_new_type'))).toBe('\u201CSign\u201D (brand_new_type) was added on page 1.');
    });

    it('shows an unknown kind as its code, so nothing is hidden', () => {
        expect(describeChange(en, change('brand_new_kind', 'question', 'T'))).toBe('brand_new_kind');
    });

    it('never builds markup from content: values stay text', () => {
        const text = describeChange(en, change('title_changed', 'question', '<img src=x onerror=alert(1)>', { before: '<b>a</b>', after: '<img src=x onerror=alert(1)>' }));
        expect(text).toContain('<img src=x onerror=alert(1)>');
        expect(typeof text).toBe('string');
    });
});

describe('groupChanges', () => {
    it('puts the form first, then pages, then questions, leaving empty groups out', () => {
        const groups = groupChanges([change('title_changed', 'question', 'a'), change('form_title_changed', 'form', null), change('question_added', 'question', 'b')]);
        expect(groups.map((g) => [g.scope, g.changes.length])).toEqual([
            ['form', 1],
            ['question', 2]
        ]);
        expect(groupChanges([])).toEqual([]);
    });
});
