import { describe, expect, it } from 'vitest';

import { FieldTypes, StandardFormDto, StandardFormFieldDto, StandardFormResponseDto } from '@app/models/dtos/form';
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

const form = (hiddenFields?: string[]) => ({ formId: 'f', title: 'Survey', builderVersion: 'v2', fields: slide([name, phone, colours]), hiddenFields }) as unknown as StandardFormDto;

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
    it('puts submission time, response id and hidden fields at the end of each row', () => {
        const { main, groupTables } = buildResponsesExport(form(['utm_source', 'ref']), sample);
        expect(main.headers).toEqual(['Responder ID', 'Name', 'Phone', 'Colours', 'Submitted at (UTC, ISO 8601)', 'Response ID', 'Hidden: utm_source', 'Hidden: ref']);
        expect(main.rows).toEqual([
            ['sita@example.org', 'Sita', '+31 6 1234 5678', 'Red; Blue', '2026-10-01T10:00:05Z', 'resp-1', 'newsletter', '=SUM(1)'],
            ['Anonymous', 'Ram', '', '', '2026-10-02T08:30:00Z', 'resp-2', '', '']
        ]);
        expect(groupTables).toEqual([]);
    });

    it('has no hidden-field columns when the form declares none, and ignores undeclared values', () => {
        const { main } = buildResponsesExport(form(), sample);
        expect(main.headers.slice(-2)).toEqual(['Submitted at (UTC, ISO 8601)', 'Response ID']);
        expect(main.rows[0]).toHaveLength(main.headers.length);
        expect(main.rows[0]).not.toContain('newsletter');
    });

    it('lists a declared hidden field once', () => {
        const { main } = buildResponsesExport(form(['ref', 'ref']), sample);
        expect(main.headers.filter((h) => h === 'Hidden: ref')).toHaveLength(1);
    });

    it('writes Anonymous, never "- -"', () => {
        const csv = tableToCsv(buildResponsesExport(form(), sample).main);
        expect(csv).toContain('Anonymous,');
        expect(csv).not.toContain('- -');
    });

    it('joins a multi-select with "; " so the cell stays one column', () => {
        const csv = tableToCsv(buildResponsesExport(form(), sample).main);
        expect(csv.split('\r\n')[1]).toBe('sita@example.org,Sita,+31 6 1234 5678,Red; Blue,2026-10-01T10:00:05Z,resp-1');
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
    // [value, kept as is]
    const cases: Array<[string, boolean]> = [
        // formulas and tricks: always prefixed
        ["-2+3+cmd|' /C calc'!A0", false],
        ['+HYPERLINK("http://x","y")', false],
        ['=SUM(1)', false],
        ['=1+1', false],
        ['@x', false],
        ['@SUM(A1)', false],
        ['\tx', false],
        ['\r=1', false],
        ['\t', false],
        ['\r', false],
        ['-', false],
        ['+', false],
        ['-abc', false],
        ['+1+cmd', false],
        ['-1;=1', false],
        ['+1\n=1', false],
        ['-1\t', false],
        ['+31 6 1234 5678 ext', false],
        ['+31 6 1234 5678=', false],
        ['-1|2', false],
        ['+1e5', false],
        ['-١٢', false],
        // strict whole-value numbers and phone numbers: left alone
        ['+31 6 1234 5678', true],
        ['+31612345678', true],
        ['-12.5', true],
        ['-12', true],
        ['+1 (555) 123-4567', true],
        ['(020) 123-4567', true],
        ['020 123 4567', true],
        ['+31-6-1234-5678', true],
        // not starting with a formula character: left alone
        ['plain', true],
        ['', true],
        ['a=b', true],
        ['1+1', true],
        [' =1', true],
        ['2026-10-01T10:00:00Z', true]
    ];
    it.each(cases)('%j kept as is: %s', (value, kept) => {
        expect(formulaSafeCell(value)).toBe(kept ? value : `'${value}`);
    });

    it('leaves numbers alone', () => {
        expect(formulaSafeCell(-5)).toBe(-5);
        expect(formulaSafeCell(0)).toBe(0);
    });

    it('guards hidden-field values (they come from the link query string)', () => {
        const csv = tableToCsv(buildResponsesExport(form(['=cmd', 'ref']), sample).main);
        const [header, first] = csv.split('\r\n');
        expect(header.endsWith(',Hidden: =cmd,Hidden: ref')).toBe(true);
        expect(first.endsWith(",'=SUM(1)")).toBe(true);
        expect(first).toContain(',+31 6 1234 5678,');
    });
});
