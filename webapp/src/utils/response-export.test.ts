import { describe, expect, it } from 'vitest';

import { FieldTypes, StandardFormDto, StandardFormFieldDto, StandardFormResponseDto } from '@app/models/dtos/form';
import { getAnswerForField } from '@app/utils/form-builder-block-utils';
import { buildResponsesExport, formulaSafeCell, submittedAtCell, tableToCsv } from '@app/utils/response-export';

const slide = (fields: StandardFormFieldDto[]): StandardFormFieldDto[] => [{ id: 's1', index: 0, type: FieldTypes.SLIDE, properties: { fields } }];
const name: StandardFormFieldDto = { id: 'name', index: 0, type: FieldTypes.SHORT_TEXT, title: 'Name' };
const phone: StandardFormFieldDto = { id: 'phone', index: 1, type: FieldTypes.PHONE_NUMBER, title: 'Phone' };
const colours: StandardFormFieldDto = {
    id: 'colours',
    index: 2,
    type: FieldTypes.MULTIPLE_CHOICE,
    title: 'Colours',
    properties: {
        allowMultipleSelection: true,
        choices: [
            { id: 'c1', value: 'Red' },
            { id: 'c2', value: 'Green' },
            { id: 'c3', value: 'Blue' }
        ]
    }
};

const form = (hiddenFields?: string[], fields: StandardFormFieldDto[] = [name, phone, colours]) => ({ formId: 'f', title: 'Survey', builderVersion: 'v2', fields: slide(fields), hiddenFields }) as unknown as StandardFormDto;

const response = (over: Record<string, any>) => ({ responseId: 'r', answers: {}, createdAt: '2026-10-01T10:00:00Z', ...over }) as unknown as StandardFormResponseDto;

const sample: StandardFormResponseDto[] = [
    response({
        responseId: 'resp-1',
        dataOwnerIdentifier: 'sita@example.org',
        createdAt: '2026-10-01T10:00:05',
        hiddenFields: { utm_source: 'newsletter', ref: '=SUM(1)' },
        answers: { name: { type: 'text', text: 'Sita' }, phone: { type: 'phone_number', phone_number: '+31 6 1234 5678' }, colours: { type: 'choices', choices: { values: ['c1', 'c3'] } } }
    }),
    response({ responseId: 'resp-2', createdAt: new Date('2026-10-02T08:30:00Z'), answers: { name: { type: 'text', text: 'Ram' } } })
];

describe('export columns', () => {
    it('puts response id, submission time and hidden fields at the end of each row', () => {
        const { main, groupTables } = buildResponsesExport(form(['utm_source', 'ref']), sample);
        expect(main.headers).toEqual(['Responder ID', 'Name', 'Phone', 'Colours', 'Response ID', 'Submitted at (UTC, ISO 8601)', 'Hidden: utm_source', 'Hidden: ref']);
        expect(main.rows).toEqual([
            ['sita@example.org', 'Sita', '+31 6 1234 5678', 'Red; Blue', 'resp-1', '2026-10-01T10:00:05Z', 'newsletter', '=SUM(1)'],
            ['Anonymous', 'Ram', '', '', 'resp-2', '2026-10-02T08:30:00Z', '', '']
        ]);
        expect(groupTables).toEqual([]);
    });

    it('has no hidden-field columns when the form declares none, and ignores undeclared values', () => {
        const { main } = buildResponsesExport(form(), sample);
        expect(main.headers.slice(-2)).toEqual(['Response ID', 'Submitted at (UTC, ISO 8601)']);
        expect(main.rows[0]).toHaveLength(main.headers.length);
        expect(main.rows[0]).not.toContain('newsletter');
    });

    it('lists a declared hidden field once', () => {
        const { main } = buildResponsesExport(form(['ref', 'ref']), sample);
        expect(main.headers.filter((h) => h === 'Hidden: ref')).toHaveLength(1);
    });

    it('reads only own string or number hidden values, never inherited properties or objects', () => {
        const hidden = Object.create({ inherited: 'leak' });
        Object.assign(hidden, { n: 5, obj: { a: 1 }, flag: true, ok: 'yes' });
        const { main } = buildResponsesExport(form(['constructor', '__proto__', 'toString', 'inherited', 'n', 'obj', 'flag', 'ok', 'missing']), [response({ hiddenFields: hidden }), response({ hiddenFields: undefined })]);
        expect(main.rows[0].slice(-9)).toEqual(['', '', '', '', 5, '', '', 'yes', '']);
        expect(main.rows[1].slice(-9)).toEqual(['', '', '', '', '', '', '', '', '']);
        const proto = JSON.parse('{"__proto__": "own-proto"}');
        expect(buildResponsesExport(form(['__proto__']), [response({ hiddenFields: proto })]).main.rows[0].slice(-1)).toEqual(['own-proto']);
    });

    it('writes Anonymous, never "- -"', () => {
        const csv = tableToCsv(buildResponsesExport(form(), sample).main);
        expect(csv).toContain('Anonymous,');
        expect(csv).not.toContain('- -');
    });

    it('joins a multi-select with "; " so the cell stays one column', () => {
        const csv = tableToCsv(buildResponsesExport(form(), sample).main);
        expect(csv.split('\r\n')[1]).toBe("sita@example.org,Sita,'+31 6 1234 5678,Red; Blue,resp-1,2026-10-01T10:00:05Z");
    });

    it('writes an empty Response ID when the response has none', () => {
        const { main } = buildResponsesExport(form(), [response({ responseId: undefined })]);
        expect(main.rows[0].slice(-2)).toEqual(['', '2026-10-01T10:00:00Z']);
    });

    it('joins a multi-select inside a repeating group item with "; "', () => {
        const grp: StandardFormFieldDto = { id: 'g', index: 3, type: FieldTypes.GROUP, title: 'Kids', properties: { repeat: { minItems: 1, maxItems: 2, itemLabel: 'Kid' }, fields: [colours] } };
        const answers = { g: { type: 'group', items: [{ colours: { type: 'choices', choices: { values: ['c1', 'c2'] } } }] } };
        const { main } = buildResponsesExport(form(undefined, [grp]), [response({ answers })]);
        expect(main.headers.slice(1, 3)).toEqual(['Kid 1 – Colours', 'Kid 2 – Colours']);
        expect(main.rows[0].slice(1, 3)).toEqual(['Red; Green', '']);
    });

    it('joins a multi-select in a staff (internal) field with "; "', () => {
        const staffColours = { ...colours, id: 'sc', title: 'Tags', internal: true } as StandardFormFieldDto;
        const { main } = buildResponsesExport(form(undefined, [name, staffColours]), [response({ answers: {}, internalAnswers: { sc: { type: 'choices', choices: { values: ['c2', 'c3'] } } } })]);
        expect(main.headers).toContain('Internal: Tags');
        expect(main.rows[0][main.headers.indexOf('Internal: Tags')]).toBe('Green; Blue');
    });

    it('suffixes a new header with " (2)" when a question already uses the name', () => {
        const clash = (id: string, title: string): StandardFormFieldDto => ({ id, index: 9, type: FieldTypes.SHORT_TEXT, title });
        const f = form(['x'], [clash('a', 'Response ID'), clash('b', 'Hidden: x'), clash('c', 'Submitted at (UTC, ISO 8601)')]);
        const { main } = buildResponsesExport(f, [response({ hiddenFields: { x: 'v' } })]);
        expect(main.headers).toEqual(['Responder ID', 'Response ID', 'Hidden: x', 'Submitted at (UTC, ISO 8601)', 'Response ID (2)', 'Submitted at (UTC, ISO 8601) (2)', 'Hidden: x (2)']);
        expect(new Set(main.headers).size).toBe(main.headers.length);
    });
});

describe('getAnswerForField separators', () => {
    const answers = { colours: { type: 'choices', choices: { values: ['c1', 'c3'] } } };
    it('keeps the display separator without one', () => {
        expect(getAnswerForField({ answers } as any, colours)).toBe('Red,Blue');
    });
    it('uses the given separator', () => {
        expect(getAnswerForField({ answers } as any, colours, '; ')).toBe('Red; Blue');
    });
    it('keeps ", " for checkboxes and ranking without a separator', () => {
        const checkboxes = {
            id: 'cb',
            type: 'input_checkboxes',
            properties: {
                choices: [
                    { id: 'a', value: 'A' },
                    { id: 'b', value: 'B' }
                ]
            }
        } as unknown as StandardFormFieldDto;
        const response = { answers: { cb: { choices: { values: ['A', 'B'] } } } } as any;
        expect(getAnswerForField(response, checkboxes)).toBe('A, B');
        expect(getAnswerForField(response, checkboxes, '; ')).toBe('A; B');
    });
});

describe('submittedAtCell', () => {
    it.each([
        ['2026-10-01T10:00:00Z', '2026-10-01T10:00:00Z'],
        ['2026-10-01T10:00:00.123456', '2026-10-01T10:00:00Z'],
        ['2026-10-01T12:00:00+02:00', '2026-10-01T10:00:00Z'],
        [new Date('2026-10-01T10:00:00Z'), '2026-10-01T10:00:00Z'],
        [undefined, ''],
        [null, ''],
        ['not a date', '']
    ])('%s -> %s', (input, expected) => {
        expect(submittedAtCell(input as any)).toBe(expected);
    });
});

describe('formula guard', () => {
    const kept: string[] = ['-12.5', '-3', '-0', '-10.25', 'plain', '', 'a=b', '1+1', '2026-10-01T10:00:00Z', '(020) 123-4567', '020 123 4567', '31612345678'];
    const prefixed: string[] = [
        "-2+3+cmd|' /C calc'!A0",
        '+HYPERLINK("http://x","y")',
        '=SUM(1)',
        '=1+1',
        '@x',
        '@SUM(A1)',
        '\tx',
        '\r=1',
        '\t',
        '\r',
        '-',
        '+',
        '-abc',
        '+1+cmd',
        '-1;=1',
        '-1-1',
        '-1.',
        '-.5',
        '-1.2.3',
        '-1e5',
        '-1\n',
        '-1 ',
        '- 1',
        '+1\n=1',
        '+31 6 1234 5678',
        '+31612345678',
        '+31-6-1234-5678',
        '+1 (555) 123-4567',
        '+12.5',
        '-1|2',
        '-١٢',
        ' =1',
        '  +1',
        '\n=1',
        ' \n-cmd',
        ' =1',
        ' @x'
    ];
    it.each(kept)('%j is left alone', (value) => {
        expect(formulaSafeCell(value)).toBe(value);
    });
    it.each(prefixed)('%j gets a leading apostrophe', (value) => {
        expect(formulaSafeCell(value)).toBe(`'${value}`);
    });

    it('leaves numbers alone', () => {
        expect(formulaSafeCell(-5)).toBe(-5);
        expect(formulaSafeCell(0)).toBe(0);
    });

    it('guards header cells that start with a formula character', () => {
        const csv = tableToCsv({ name: 't', headers: ['=cmd', '+31', 'Hidden: =cmd'], rows: [] });
        expect(csv).toBe("'=cmd,'+31,Hidden: =cmd");
    });

    it('guards hidden-field values (they come from the link query string)', () => {
        const csv = tableToCsv(buildResponsesExport(form(['=cmd', 'ref']), sample).main);
        const [header, first] = csv.split('\r\n');
        expect(header.endsWith(',Hidden: =cmd,Hidden: ref')).toBe(true);
        expect(first.endsWith(",,'=SUM(1)")).toBe(true);
        expect(first).toContain(",'+31 6 1234 5678,");
    });
});
