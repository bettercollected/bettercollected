import moment from 'moment';

import { FieldTypes, StandardFormDto, StandardFormFieldDto, StandardFormResponseDto } from '@app/models/dtos/form';
import { calculatedAnswerValue } from '@app/utils/calculated-fields';
import { getAnswerForField, getFormFields, getTitleForHeader } from '@app/utils/form-builder-block-utils';
import { getInternalAnswerText, getInternalColumnTitle, getInternalFields } from '@app/utils/internal-fields';
import { getGroupChildren, getGroupItems, getRepeatSettings, isRepeatingGroup } from '@app/utils/repeating-groups';

/**
 * Flatten responses into export tables (CSV today; the Google Sheets action
 * follows the same rule server side, temporal/actions-executor/utilities/form.py).
 *
 * Repeating groups:
 *  - `columns` layout (default when maxItems <= 5): columns per item —
 *    "Applicant 1 – Name", "Applicant 2 – Name" — one row per submission.
 *  - `rows` layout (default above 5): the main table gets the item count, and
 *    the group gets a table of its own with the response id and item number,
 *    one row per item. The main table then ends with a Response ID column so
 *    the two can be joined.
 */

export type ExportCell = string | number;

export interface ExportTable {
    /** Table name ("Responses" or the group title) — used for file names. */
    name: string;
    headers: string[];
    rows: ExportCell[][];
}

export interface ResponsesExport {
    main: ExportTable;
    groupTables: ExportTable[];
}

export const RESPONDER_ID_COLUMN = 'Responder ID';
export const RESPONSE_ID_COLUMN = 'Response ID';
export const SUBMITTED_AT_COLUMN = 'Submitted at (UTC, ISO 8601)';
export const HIDDEN_COLUMN_PREFIX = 'Hidden: ';
/** What the responder column says when the responder did not give an email. */
export const ANONYMOUS_LABEL = 'Anonymous';
/** Joins the options of a multi-select answer inside one cell (a comma would read as a column break). */
export const LIST_SEPARATOR = '; ';

const cell = (value: any): ExportCell => (value === undefined || value === null ? '' : typeof value === 'number' ? value : String(value));

/** Child questions that collect an answer (statements are skipped). */
function exportableChildren(group: StandardFormFieldDto): StandardFormFieldDto[] {
    return getGroupChildren(group).filter((child) => child?.type !== FieldTypes.TEXT && child?.type !== FieldTypes.IMAGE_CONTENT && child?.type !== FieldTypes.VIDEO_CONTENT);
}

/** Answer of one child question in one item, formatted like any other answer (multi-select joined with the export's '; ' unless the screen passes its own). */
export function getItemAnswer(item: Record<string, any> | undefined, child: StandardFormFieldDto, listSeparator: string = LIST_SEPARATOR): ExportCell {
    return cell(getAnswerForField({ answers: item ?? {} } as StandardFormResponseDto, child, listSeparator));
}

/** A captured hidden-field value: only the response's own string or number values, never an inherited property like "constructor". */
function hiddenValue(values: Record<string, string> | undefined, name: string): ExportCell {
    if (!values || !Object.prototype.hasOwnProperty.call(values, name)) return '';
    const value: unknown = values[name];
    return typeof value === 'string' || typeof value === 'number' ? value : '';
}

/** UTC, ISO 8601, to the second: "2026-10-01T10:00:00Z". Sorts and joins in a spreadsheet. */
export function submittedAtCell(value: string | Date | undefined | null): string {
    if (!value) return '';
    const date = moment.utc(value);
    return date.isValid() ? date.format('YYYY-MM-DDTHH:mm:ss[Z]') : '';
}

export function buildResponsesExport(form: StandardFormDto, responses: StandardFormResponseDto[]): ResponsesExport {
    const fields = getFormFields(form);
    const title = (field: StandardFormFieldDto) => getTitleForHeader(field, form) ?? '';

    const headers: string[] = [RESPONDER_ID_COLUMN];
    const groupTables: Array<ExportTable & { group: StandardFormFieldDto; children: StandardFormFieldDto[] }> = [];

    fields.forEach((field) => {
        if (!isRepeatingGroup(field)) {
            headers.push(title(field));
            return;
        }
        const { maxItems, itemLabel, exportLayout } = getRepeatSettings(field);
        const children = exportableChildren(field);
        if (exportLayout === 'rows') {
            headers.push(`${title(field)} (${itemLabel} count)`);
            groupTables.push({ group: field, children, name: title(field), headers: [RESPONSE_ID_COLUMN, itemLabel, ...children.map(title)], rows: [] });
            return;
        }
        for (let i = 0; i < maxItems; i++) children.forEach((child) => headers.push(`${itemLabel} ${i + 1} – ${title(child)}`));
    });
    // Internal (staff-entered) columns, after the respondent's answers.
    const internalFields = getInternalFields(form);
    internalFields.forEach((field) => headers.push(getInternalColumnTitle(field)));
    // The response's own data goes at the END of the row, so the columns a
    // script already reads by position do not move: response id (also the key
    // of the group tables, where it keeps its old place), submission time,
    // then one column per declared hidden field. One place, so the order is
    // easy to change. A new header that a question title already uses gets
    // " (2)", so two columns never share a name.
    const hiddenNames = Array.from(new Set(form.hiddenFields ?? []));
    const taken = new Set(headers);
    const uniqueHeader = (header: string) => (taken.has(header) ? `${header} (2)` : header);
    headers.push(uniqueHeader(RESPONSE_ID_COLUMN), uniqueHeader(SUBMITTED_AT_COLUMN), ...hiddenNames.map((name) => uniqueHeader(HIDDEN_COLUMN_PREFIX + name)));

    const rows = responses.map((response) => {
        const row: ExportCell[] = [response?.dataOwnerIdentifier || ANONYMOUS_LABEL];
        fields.forEach((field) => {
            if (field.type === FieldTypes.CALCULATED) {
                // the stored value as is: numbers stay numbers in a spreadsheet
                const value = calculatedAnswerValue(response.answers?.[field.id]);
                row.push(cell(typeof value === 'boolean' ? (value ? 'Yes' : 'No') : value));
                return;
            }
            if (!isRepeatingGroup(field)) {
                row.push(cell(getAnswerForField(response, field, LIST_SEPARATOR)));
                return;
            }
            const { maxItems, exportLayout } = getRepeatSettings(field);
            const items = getGroupItems(response.answers, field.id);
            if (exportLayout === 'rows') {
                row.push(items.length);
                const table = groupTables.find((t) => t.group.id === field.id)!;
                items.forEach((item, index) => table.rows.push([response.responseId, index + 1, ...table.children.map((child) => getItemAnswer(item, child))]));
                return;
            }
            const children = exportableChildren(field);
            for (let i = 0; i < maxItems; i++) children.forEach((child) => row.push(getItemAnswer(items[i], child)));
        });
        internalFields.forEach((field) => row.push(cell(getInternalAnswerText(response, field, LIST_SEPARATOR))));
        row.push(cell(response.responseId), submittedAtCell(response.createdAt));
        hiddenNames.forEach((name) => row.push(hiddenValue(response.hiddenFields, name)));
        return row;
    });

    return {
        main: { name: 'Responses', headers, rows },
        groupTables: groupTables.map(({ name, headers, rows }) => ({ name, headers, rows }))
    };
}

/** A plain negative decimal ("-3", "-12.5"): the only value starting with a guard character that is left alone. */
const NEGATIVE_NUMBER = /^-[0-9]+(\.[0-9]+)?$/;

/**
 * Spreadsheet apps run cells starting with = + - @ (also after leading
 * whitespace) or a tab / CR as formulas. Respondent text must never become
 * one: such string cells get a leading `'`, which spreadsheets treat as "this
 * is text". Numbers, and plain negative decimals, are left as they are.
 * Everything else is prefixed, phone numbers starting with "+" included: a
 * visible apostrophe keeps the data intact, while a phone number a
 * spreadsheet evaluates ("+31-6-1234-5678" is a subtraction) is corrupted.
 */
export function formulaSafeCell(value: ExportCell): ExportCell {
    if (typeof value !== 'string') return value;
    if (NEGATIVE_NUMBER.test(value)) return value;
    return /^[\t\r]|^\s*[=+\-@]/.test(value) ? `'${value}` : value;
}

/** RFC 4180 CSV text of a table, with formula-like cells neutralised. */
export function tableToCsv(table: ExportTable): string {
    const escape = (value: ExportCell) => {
        const text = String(formulaSafeCell(value) ?? '');
        return /[",\r\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
    };
    return [table.headers, ...table.rows].map((row) => row.map(escape).join(',')).join('\r\n');
}

/** A file-name-safe version of a table name. */
export function exportFileName(formTitle: string, tableName?: string): string {
    const safe = (text: string) => text.replace(/[\\/:*?"<>|]+/g, ' ').trim() || 'export';
    return tableName ? `${safe(formTitle)} - ${safe(tableName)}.csv` : `${safe(formTitle)}.csv`;
}
