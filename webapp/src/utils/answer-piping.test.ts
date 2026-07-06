import { describe, expect, it } from 'vitest';

import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import { captureHiddenFieldValues, getPrefillEntries, pruneOrphanedPipes, resolvePipesInText, resolvePipesInTitle, resolvePipeValue, titleHasPipes } from './answer-piping';

const slide = (index: number, fields: Array<Partial<StandardFormFieldDto>>): StandardFormFieldDto =>
    ({
        id: `slide-${index}`,
        index,
        type: FieldTypes.SLIDE,
        properties: { fields: fields as Array<StandardFormFieldDto> }
    }) as StandardFormFieldDto;

const SLIDES = [
    slide(0, [
        { id: 'name-field', index: 0, type: FieldTypes.SHORT_TEXT },
        { id: 'email-field', index: 1, type: FieldTypes.EMAIL },
        { id: 'toppings-field', index: 2, type: FieldTypes.MULTIPLE_CHOICE, properties: { allowMultipleSelection: true } as any }
    ]),
    slide(1, [{ id: 'rating-field', index: 0, type: FieldTypes.RATING }])
];

const ANSWERS = {
    'name-field': { text: 'Ada' },
    'email-field': { email: 'ada@example.com' },
    'toppings-field': { choices: { values: ['Olives', 'Feta'] } },
    'rating-field': { number: 4 }
};

const CTX = { slides: SLIDES, answers: ANSWERS, hiddenValues: { utm_source: 'newsletter' } };

describe('resolvePipeValue', () => {
    it('resolves field answers using the field type', () => {
        expect(resolvePipeValue('field', 'name-field', CTX)).toBe('Ada');
        expect(resolvePipeValue('field', 'rating-field', CTX)).toBe('4');
    });

    it('joins multi-choice answers with commas', () => {
        expect(resolvePipeValue('field', 'toppings-field', CTX)).toBe('Olives, Feta');
    });

    it('resolves hidden fields from captured URL values', () => {
        expect(resolvePipeValue('hidden', 'utm_source', CTX)).toBe('newsletter');
    });

    it('returns undefined for unanswered, unknown, or empty values', () => {
        expect(resolvePipeValue('field', 'missing-field', CTX)).toBeUndefined();
        expect(resolvePipeValue('hidden', 'nope', CTX)).toBeUndefined();
        expect(resolvePipeValue('field', 'name-field', { ...CTX, answers: {} })).toBeUndefined();
    });
});

describe('resolvePipesInText', () => {
    it('replaces field and hidden tokens', () => {
        expect(resolvePipesInText('Thanks, {{field:name-field}}! Came from {{hidden:utm_source}}.', CTX)).toBe('Thanks, Ada! Came from newsletter.');
    });

    it('uses the fallback when there is no value, empty string otherwise', () => {
        expect(resolvePipesInText('Hi {{field:missing|there}}!', CTX)).toBe('Hi there!');
        expect(resolvePipesInText('Hi {{field:missing}}!', CTX)).toBe('Hi !');
    });

    it('leaves text without tokens untouched', () => {
        expect(resolvePipesInText('No tokens here', CTX)).toBe('No tokens here');
        expect(resolvePipesInText(undefined, CTX)).toBeUndefined();
    });
});

describe('resolvePipesInTitle', () => {
    const title = {
        type: 'doc',
        content: [
            {
                type: 'paragraph',
                content: [{ type: 'text', text: 'Thanks, ' }, { type: 'answerPipe', attrs: { kind: 'field', pipeKey: 'name-field', label: 'Name', fallback: '' } }, { type: 'text', text: '!' }]
            }
        ]
    };

    it('replaces pipe nodes with the resolved answer text', () => {
        const resolved = resolvePipesInTitle(title, CTX) as any;
        expect(resolved.content[0].content.map((n: any) => n.text).join('')).toBe('Thanks, Ada!');
        expect(resolved.content[0].content.every((n: any) => n.type === 'text')).toBe(true);
    });

    it('keeps marks from the pipe node on the replacement text', () => {
        const boldPipe = {
            type: 'doc',
            content: [{ type: 'paragraph', content: [{ type: 'answerPipe', attrs: { kind: 'hidden', pipeKey: 'utm_source' }, marks: [{ type: 'bold' }] }] }]
        };
        const resolved = resolvePipesInTitle(boldPipe, CTX) as any;
        expect(resolved.content[0].content[0]).toEqual({ type: 'text', text: 'newsletter', marks: [{ type: 'bold' }] });
    });

    it('drops the node entirely when unresolved with no fallback (tiptap forbids empty text nodes)', () => {
        const orphan = {
            type: 'doc',
            content: [{ type: 'paragraph', content: [{ type: 'text', text: 'Hi ' }, { type: 'answerPipe', attrs: { kind: 'field', pipeKey: 'missing' } }] }]
        };
        const resolved = resolvePipesInTitle(orphan, CTX) as any;
        expect(resolved.content[0].content).toHaveLength(1);
    });

    it('does not mutate the stored title', () => {
        const before = JSON.stringify(title);
        resolvePipesInTitle(title, CTX);
        expect(JSON.stringify(title)).toBe(before);
    });

    it('resolves text tokens in legacy plain-string titles', () => {
        expect(resolvePipesInTitle('Hello {{field:name-field}}', CTX)).toBe('Hello Ada');
    });
});

describe('titleHasPipes', () => {
    it('detects pipe nodes and text tokens', () => {
        expect(titleHasPipes({ type: 'doc', content: [{ type: 'answerPipe' }] })).toBe(true);
        expect(titleHasPipes('Hi {{hidden:x}}')).toBe(true);
        expect(titleHasPipes({ type: 'doc', content: [{ type: 'text', text: 'plain' }] })).toBe(false);
        expect(titleHasPipes('plain')).toBe(false);
    });
});

describe('pruneOrphanedPipes', () => {
    const makeSlides = () => [
        slide(0, [
            { id: 'a', index: 0, type: FieldTypes.SHORT_TEXT },
            {
                id: 'b',
                index: 1,
                type: FieldTypes.SHORT_TEXT,
                title: {
                    type: 'doc',
                    content: [
                        {
                            type: 'paragraph',
                            content: [
                                { type: 'answerPipe', attrs: { kind: 'field', pipeKey: 'a' } },
                                { type: 'answerPipe', attrs: { kind: 'field', pipeKey: 'deleted' } },
                                { type: 'answerPipe', attrs: { kind: 'hidden', pipeKey: 'utm_source' } },
                                { type: 'text', text: 'question' }
                            ]
                        }
                    ]
                }
            }
        ])
    ];

    it('removes pipes referencing deleted fields, keeps live ones', () => {
        const slides = makeSlides();
        pruneOrphanedPipes(slides);
        const content = (slides[0].properties!.fields![1].title as any).content[0].content;
        expect(content.map((n: any) => n.type)).toEqual(['answerPipe', 'answerPipe', 'text']);
        expect(content[0].attrs.pipeKey).toBe('a');
        expect(content[1].attrs.pipeKey).toBe('utm_source');
    });

    it('prunes hidden pipes only when the declared list is given', () => {
        const slides = makeSlides();
        pruneOrphanedPipes(slides, []);
        const content = (slides[0].properties!.fields![1].title as any).content[0].content;
        expect(content.map((n: any) => n.attrs?.pipeKey ?? n.type)).toEqual(['a', 'text']);
    });
});

describe('captureHiddenFieldValues', () => {
    it('captures only declared, non-empty parameters', () => {
        const captured = captureHiddenFieldValues(['utm_source', 'utm_medium', 'name'], '?utm_source=x&utm_medium=&other=y&name=Ada');
        expect(captured).toEqual({ utm_source: 'x', name: 'Ada' });
    });

    it('captures nothing when the form declares nothing', () => {
        expect(captureHiddenFieldValues(undefined, '?utm_source=x')).toEqual({});
    });
});

describe('getPrefillEntries', () => {
    it('maps field_<id> params to real answerable fields', () => {
        const entries = getPrefillEntries(SLIDES, '?field_name-field=Ada&field_unknown=x&name-field=nope');
        expect(entries).toHaveLength(1);
        expect(entries[0].field.id).toBe('name-field');
        expect(entries[0].value).toBe('Ada');
    });
});
