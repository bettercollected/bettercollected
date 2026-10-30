import { ThemeColors } from '@app/constants/theme';
import { FieldTypes, StandardFormDto, StandardFormFieldDto, StandardFormResponseDto } from '@app/models/dtos/form';
import { Comparison, LogicalOperator } from '@app/models/types/form-builder-shared';

// Made-up data for the response page tests: a themed, three-page form with every
// field type the builder offers, and responses to it.

const choices = (...values: string[]) => values.map((value, index) => ({ id: `c-${values[0].slice(0, 2).toLowerCase()}${index}`, value }));
const field = (id: string, type: FieldTypes, title: string, properties: any = {}, extra: Partial<StandardFormFieldDto> = {}): StandardFormFieldDto =>
    ({ id, index: 0, type, title, properties: { fields: [], ...properties }, validations: {}, ...extra }) as StandardFormFieldDto;

export const COLOUR_CHOICES = choices('Red', 'Green', 'Blue');
export const FRUIT_CHOICES = choices('Apple', 'Pear', 'Plum');
export const COUNTRY_CHOICES = choices('Netherlands', 'Belgium');

const matrixRow = (id: string, title: string, index: number) => ({
    id,
    index,
    type: FieldTypes.MATRIX_ROW_INPUT,
    title,
    properties: {
        fields: [],
        choices: [
            { id: `${id}-poor`, value: 'Poor' },
            { id: `${id}-great`, value: 'Great' }
        ]
    }
});

export const PAGE_ONE: StandardFormFieldDto[] = [
    field('intro', FieldTypes.TEXT, 'Welcome to the summer meeting'),
    field('name', FieldTypes.SHORT_TEXT, 'What is your name?', {}, { description: 'As on your badge' }),
    field('email', FieldTypes.EMAIL, 'What is your email address?'),
    field('phone', FieldTypes.PHONE_NUMBER, 'Your phone number'),
    field('people', FieldTypes.NUMBER, 'How many people?'),
    field('about', FieldTypes.LONG_TEXT, 'Tell us more'),
    field('arrival', FieldTypes.DATE, 'When do you arrive?'),
    field('site', FieldTypes.LINK, 'Your website'),
    field('country', FieldTypes.DROP_DOWN, 'Which country?', { choices: COUNTRY_CHOICES }),
    field('colour', FieldTypes.MULTIPLE_CHOICE, 'Favourite colour?', { choices: COLOUR_CHOICES, allowOtherChoice: true }),
    field('fruit', FieldTypes.MULTIPLE_CHOICE, 'Which fruits?', { choices: FRUIT_CHOICES, allowMultipleSelection: true }),
    field('agree', FieldTypes.YES_NO, 'Do you agree?')
];

export const PAGE_TWO: StandardFormFieldDto[] = [
    field('rating', FieldTypes.RATING, 'Rate the service', { steps: 5 }),
    field('scale', FieldTypes.LINEAR_RATING, 'How likely are you to return?', { steps: 5, startFrom: 1 }),
    field('matrix', FieldTypes.MATRIX, 'Rate each part', { fields: [matrixRow('m1', 'Quality', 0), matrixRow('m2', 'Speed', 1)] }),
    field('table', FieldTypes.TABULAR_INPUT, 'Your expenses', { rowTitles: ['Travel', 'Food'], columnTitles: ['Amount', 'Note'] }),
    field('cv', FieldTypes.FILE_UPLOAD, 'Upload your CV'),
    field('guests', FieldTypes.GROUP, 'Your guests', {
        repeat: { minItems: 0, maxItems: 3, itemLabel: 'Guest' },
        fields: [field('guest-name', FieldTypes.SHORT_TEXT, 'Guest name'), field('guest-diet', FieldTypes.MULTIPLE_CHOICE, 'Diet', { choices: choices('Vegan', 'Any') })]
    }),
    field('total', FieldTypes.CALCULATED, 'Total', { expression: { '+': [1, 2] }, format: { style: 'currency', currency: 'EUR', decimals: 2 } }),
    // shown only to someone who disagreed
    field('why', FieldTypes.SHORT_TEXT, 'Why not?', {
        logic: { action: 'SHOW', operator: LogicalOperator.AND, conditions: [{ fieldId: 'agree', fieldType: FieldTypes.YES_NO, comparison: Comparison.IS_EQUAL, value: 'No' }] }
    })
];

export const PAGE_THREE: StandardFormFieldDto[] = [field('thanks', FieldTypes.SHORT_TEXT, 'Anything else?')];

const page = (id: string, index: number, fields: StandardFormFieldDto[], properties: any = {}) => ({ id, index, type: FieldTypes.SLIDE, title: `Page ${index + 1}`, properties: { fields, ...properties } }) as StandardFormFieldDto;

const kantlijn = ThemeColors.find((theme) => theme.title === 'Kantlijn')!;

export const FORM: StandardFormDto = {
    formId: 'form-1',
    title: 'Summer meeting registration',
    builderVersion: 'v2',
    version: 3,
    theme: kantlijn,
    hiddenFields: ['source'],
    settings: { provider: 'self' },
    fields: [page('p1', 0, PAGE_ONE, { showQuestionNumbers: true }), page('p2', 1, PAGE_TWO, { showQuestionNumbers: true }), page('p3', 2, PAGE_THREE, { showQuestionNumbers: true })]
} as any;

const answer = (id: string, type: string, rest: Record<string, any>) => ({ field: { id }, type, ...rest });

export const ANSWERS = {
    name: answer('name', 'short_text', { text: 'Anna Example' }),
    email: answer('email', 'email', { email: 'anna@example.com' }),
    phone: answer('phone', 'phone_number', { phone_number: '+31612345678' }),
    people: answer('people', 'number', { number: 0 }),
    about: answer('about', 'long_text', { text: 'First line\nSecond line' }),
    arrival: answer('arrival', 'date', { date: '2026-07-04' }),
    site: answer('site', 'url', { url: 'https://example.com/anna' }),
    country: answer('country', 'dropdown', { choice: { value: COUNTRY_CHOICES[1].id } }),
    colour: answer('colour', 'multiple_choice', { choice: { other: 'Teal' } }),
    fruit: answer('fruit', 'multiple_choice', { choices: { values: [FRUIT_CHOICES[0].id, FRUIT_CHOICES[2].id] } }),
    agree: answer('agree', 'yes_no', { boolean: true }),
    rating: answer('rating', 'rating', { number: 4 }),
    scale: answer('scale', 'linear_rating', { number: 3 }),
    m1: answer('m1', 'multiple_choice', { choice: { value: 'm1-great' } }),
    m2: answer('m2', 'multiple_choice', { choice: { value: 'm2-poor' } }),
    table: answer('table', 'tabular_input', {
        tabular_value: [
            ['12', 'train'],
            ['8', '']
        ]
    }),
    cv: answer('cv', 'file_upload', { file_metadata: { id: 'f1', name: 'cv.pdf', size: 0.2, type: 'application/pdf', url: 'https://files.example.com/signed/cv.pdf?sig=abc' } }),
    guests: answer('guests', 'group', {
        items: [{ 'guest-name': answer('guest-name', 'short_text', { text: 'Bram' }), 'guest-diet': answer('guest-diet', 'multiple_choice', { choice: { value: 'c-ve0' } }) }, { 'guest-name': answer('guest-name', 'short_text', { text: 'Cato' }) }]
    }),
    total: answer('total', 'number', { number: 42.5 })
};

export const RESPONSE: StandardFormResponseDto = {
    responseId: 'resp-1',
    formId: 'form-1',
    provider: 'self',
    createdAt: '2026-10-30T09:10:05Z',
    updatedAt: '2026-10-30T09:10:05Z',
    dataOwnerIdentifier: 'anna@example.com',
    submissionUuid: '0a1b2c3d-1111-4222-8333-444455556666',
    hiddenFields: { source: 'newsletter' },
    answers: ANSWERS
} as any;

export const ANONYMOUS_RESPONSE: StandardFormResponseDto = { ...RESPONSE, responseId: 'resp-2', dataOwnerIdentifier: null, anonymousIdentity: 'anon-1', submissionUuid: 'ffeeddcc-1111-4222-8333-444455556666' } as any;
