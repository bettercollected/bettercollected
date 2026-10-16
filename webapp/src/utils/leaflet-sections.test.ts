import { describe, expect, it } from 'vitest';

import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import { Comparison, LogicalOperator } from '@app/models/types/form-builder-shared';
import { getHiddenFieldIds } from '@app/utils/conditional-logic';

import { isNumberedQuestion, leafletSection, questionNumbers } from './leaflet-sections';

const field = (id: string, type: string = FieldTypes.SHORT_TEXT, properties: StandardFormFieldDto['properties'] = {}, title?: any): StandardFormFieldDto => ({ id, index: 0, type: type as FieldTypes, properties, title });
const text = (id: string, content: any[]) => field(id, FieldTypes.TEXT, {}, { type: 'doc', content });
const heading = (words: string) => ({ type: 'heading', attrs: { level: 2 }, content: [{ type: 'text', text: words }] });
const paragraph = (words: string) => ({ type: 'paragraph', content: [{ type: 'text', text: words }] });
const showWhenYes = { action: 'SHOW', operator: LogicalOperator.AND, conditions: [{ fieldId: 'contact', fieldType: FieldTypes.SHORT_TEXT, comparison: Comparison.IS_EQUAL, value: 'yes' }] };

/** What the respondent sees: the page's fields minus those hidden by logic. */
const visible = (fields: StandardFormFieldDto[], answers: Record<string, any>) => {
    const hidden = getHiddenFieldIds(fields, answers);
    return fields.filter((f) => !hidden.has(f.id));
};

describe('question numbers', () => {
    it('numbers questions n.1, n.2 … and skips content that asks nothing', () => {
        const page = [text('intro', [paragraph('Hello')]), field('name'), field('photo', FieldTypes.IMAGE_CONTENT), field('email', FieldTypes.EMAIL), field('upload', FieldTypes.FILE_UPLOAD)];
        expect(questionNumbers(page, 2)).toEqual({ name: '2.1', email: '2.2', upload: '2.3' });
    });

    it('counts a repeating group as one question', () => {
        const group = field('people', FieldTypes.GROUP, { repeat: { min: 1, max: 3 } as any, fields: [field('person-name')] });
        expect(isNumberedQuestion(group)).toBe(true);
        expect(questionNumbers([field('a'), group, field('b')], 1)).toEqual({ a: '1.1', people: '1.2', b: '1.3' });
    });

    it('numbers what the respondent sees: a question hidden by logic takes no number and leaves no gap', () => {
        const page = [field('contact'), field('phone', FieldTypes.PHONE_NUMBER, { logic: showWhenYes as any }), field('comments', FieldTypes.LONG_TEXT)];
        expect(questionNumbers(visible(page, {}), 3)).toEqual({ contact: '3.1', comments: '3.2' });
        // Revealed: the question takes its place, the ones after it move up.
        const yes = { contact: { type: 'text', text: 'yes' } };
        expect(questionNumbers(visible(page, yes), 3)).toEqual({ contact: '3.1', phone: '3.2', comments: '3.3' });
    });

    it('a page reached by a jump keeps its position as its section number', () => {
        // Section numbers are positions (the same as "Page x of y"), so a
        // jump from page 1 to page 3 shows section 3, never a renumbered 2.
        expect(questionNumbers([field('q')], 3)).toEqual({ q: '3.1' });
    });
});

describe('leaflet sections', () => {
    it('takes the bar title from the opening heading and leaves the rest for the band', () => {
        const opening = text('intro', [heading('About your visit'), paragraph('Tell us how it went.')]);
        const section = leafletSection([opening, field('q')], 'Visit form');
        expect(section.title).toBe('About your visit');
        expect(section.titleFromPage).toBe(true);
        expect(section.openingTextId).toBe('intro');
        expect((section.intro?.title as any).content).toEqual([paragraph('Tell us how it went.')]);
    });

    it('a heading-only opening block becomes the bar, with no band', () => {
        const section = leafletSection([text('intro', [heading('Your details')]), field('q')], 'Visit form');
        expect(section).toMatchObject({ title: 'Your details', intro: null, openingTextId: 'intro' });
    });

    it('falls back to the form title when the page opens without a heading', () => {
        expect(leafletSection([field('q')], 'Visit form')).toMatchObject({ title: 'Visit form', titleFromPage: false, intro: null, openingTextId: null });
        const plain = text('intro', [paragraph('Just some text.')]);
        expect(leafletSection([plain, field('q')], 'Visit form')).toMatchObject({ title: 'Visit form', titleFromPage: false, intro: plain, openingTextId: 'intro' });
    });

    it('ignores a text block that is not first', () => {
        expect(leafletSection([field('q'), text('later', [heading('Later')])], 'Visit form').openingTextId).toBeNull();
    });
});
