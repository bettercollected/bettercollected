// The builder's own sentences that are made in code (not in a component): in the builder's language, English as before.
import { afterEach, describe, expect, it } from 'vitest';
import i18n from 'i18next';

import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import { fieldTypeChip } from '@app/lib/field-type-name';
import { findingText } from '@app/utils/ai-build-report';
import { FormOutline, outlineProblems } from '@app/utils/ai-outline';
import { summarizeAnswerRules } from '@app/utils/answer-rules';
import { endingLabel } from '@app/utils/endings';
import { outlinePageName } from '@app/utils/form-outline';
import { describeRules, describeStaffPart, describeWithheld } from '@app/utils/pdf-import';
import { getPublishProblems } from '@app/utils/publish-checks';

afterEach(async () => {
    await i18n.changeLanguage('en');
});

const slide = (fields: Array<Partial<StandardFormFieldDto>>): StandardFormFieldDto[] => [{ id: 's1', index: 0, type: FieldTypes.SLIDE, properties: { fields: fields as StandardFormFieldDto[] } } as StandardFormFieldDto];

describe('sentences made in code, in English and Dutch', () => {
    it('names pages and endings', async () => {
        expect(outlinePageName(undefined, 1)).toBe('Page 2');
        expect(endingLabel(undefined, 0, 1)).toBe('Thank you');
        await i18n.changeLanguage('nl');
        expect(outlinePageName(undefined, 1)).toBe('Pagina 2');
        expect(endingLabel(undefined, 1, 3)).toBe('Eindpagina 2');
    });

    it('says what is wrong with an AI outline', async () => {
        const outline = { title: '', pages: [{ key: 'p', questions: [{ key: 'q', type: 'short_text', label: ' ' }] }], logic: [], jumps: [] } as unknown as FormOutline;
        expect(outlineProblems(outline)).toEqual(['Give the form a title.', 'Page 1, question 1 has no text.']);
        await i18n.changeLanguage('nl');
        expect(outlineProblems(outline)).toEqual(['Geef het formulier een titel.', 'Pagina 1, vraag 1 heeft geen tekst.']);
    });

    it('summarises answer rules', async () => {
        const field = { id: 'n', type: FieldTypes.NUMBER, validations: { minValue: 1, maxValue: 9 } } as StandardFormFieldDto;
        expect(summarizeAnswerRules(field)).toEqual(['Number from 1 to 9.']);
        await i18n.changeLanguage('nl');
        expect(summarizeAnswerRules(field)).toEqual(['Getal van 1 tot 9.']);
        const text = { id: 't', type: FieldTypes.SHORT_TEXT, validations: { minLength: 2, maxLength: 5 } } as StandardFormFieldDto;
        expect(summarizeAnswerRules(text)).toEqual(['Het antwoord heeft tussen 2 en 5 tekens.']);
    });

    it('words what must be fixed before publishing', async () => {
        const form = slide([{ id: 'e', index: 0, type: FieldTypes.EMAIL, title: 'E-mail' }]);
        expect(getPublishProblems(form)[0].message).toMatch(/^"E-mail" asks for personal details/);
        await i18n.changeLanguage('nl');
        expect(getPublishProblems(form)[0].message).toMatch(/^"E-mail" vraagt om persoonsgegevens/);
    });

    it('words the checks after building from an AI outline', async () => {
        expect(findingText('missing_title')).toBe('The form has no title.');
        expect(findingText('something_new')).toBe('Something on this form needs a look before publishing.');
        await i18n.changeLanguage('nl');
        expect(findingText('missing_title')).toBe('Het formulier heeft geen titel.');
        expect(findingText('something_new')).toBe('Er is iets op dit formulier waar u naar moet kijken voordat u publiceert.');
    });

    it('describes a PDF import report with plurals', async () => {
        expect(describeRules({ consent: 1, photo_box_to_upload: 2 })).toEqual(['1 agreement added', '2 photo boxes became an image upload']);
        expect(describeWithheld({ '2': 1 })[0].text).toBe('Page 2: 1 word inside answer boxes looked like filled-in answers and was left out of the questions. Check the questions there.');
        expect(describeStaffPart({ heading: 'Kantoor', internal_fields: 2 })).toBe('Kantoor: 2 internal fields that staff fill in on each submission. Respondents never see them.');
        await i18n.changeLanguage('nl');
        expect(describeRules({ consent: 1, photo_box_to_upload: 2 })).toEqual(['1 akkoordverklaring toegevoegd', '2 fotovakken zijn een afbeeldingsupload geworden']);
        expect(describeStaffPart({ heading: 'Kantoor', internal_fields: 1 })).toBe('Kantoor: 1 intern veld dat medewerkers bij elke inzending invullen. Respondenten zien het nooit.');
    });

    it('does not let a stored finding code pick another text', () => {
        expect(findingText('TITLE')).toBe('Something on this form needs a look before publishing.');
        expect(findingText('constructor')).toBe('Something on this form needs a look before publishing.');
    });

    it('keeps the English chip names and the flow edge words as they were', async () => {
        const t = i18n.getFixedT('en', 'builder') as unknown as Parameters<typeof fieldTypeChip>[0];
        expect(fieldTypeChip(t, 'multiple_choice')).toBe('Multiple Choice');
        expect(fieldTypeChip(t, 'date')).toBe('Calendar');
        expect(i18n.t('builder:FLOW.CMP.IS_EQUAL')).toBe('is equal');
        expect(i18n.t('builder:FLOW.CMP.LESS_THAN_EQUAL')).toBe('less than equal');
        expect(i18n.t('builder:CANVAS.FILE_TOO_LARGE')).toBe('Size greater than 25MB.');
        expect(i18n.t('builder:TRUST.PREVIEW_POLICY')).toBe('How your data is used');
        await i18n.changeLanguage('nl');
        expect(i18n.t('builder:FLOW.RESPONSES', { count: 2 })).toBe('2 reacties');
    });
});
