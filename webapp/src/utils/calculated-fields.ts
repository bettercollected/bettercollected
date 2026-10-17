import { ExprNode, ExprValue, FormulaError, evaluateExpression, formatExpressionValue, parseFormula, printFormula, validateExpression } from '@app/lib/expressions';
import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import { getComparableAnswerValue, getGroupAnswerItems } from '@app/utils/conditional-logic';

/**
 * Calculated fields: a value computed from the respondent's answers, shown
 * read-only (or kept as an "internal result" respondents never see).
 *
 * A `calculated` field stores an expressions-v1 AST at
 * `properties.expression` (docs/spec/expressions-v1.md); the builder shows it
 * as a formula (`round({Price} * 1.21, 2)`). Variables share one namespace
 * with conditional logic and answer piping: a page question's id (its answer
 * as logic reads it), `<group id>.<question id>` (a repeating group's question
 * across its items, as a list), a declared hidden field's name, and another
 * calculated field's id. Field ids win over hidden-field names.
 *
 * The respondent page writes the computed answers into the form's answers
 * (use-calculated-fields.ts), so logic, page jumps and piping read them like
 * any answer. The server recomputes every value on submit and edit and never
 * trusts these: backend services/calculated_fields.py is the twin, keep the
 * two in step.
 */

export type CalculationStyle = 'number' | 'currency' | 'percent' | 'text';

export interface CalculationFormat {
    style?: CalculationStyle;
    decimals?: number;
    currency?: string;
}

export const CALCULATION_STYLES: CalculationStyle[] = ['number', 'currency', 'percent', 'text'];
export const CALCULATION_MAX_DECIMALS = 6;
export const DEFAULT_CURRENCY = 'EUR';

/** Field types whose answer a formula cannot read (backend NOT_VARIABLES). */
const NOT_VARIABLE_TYPES = new Set<string>([
    FieldTypes.SLIDE,
    FieldTypes.MATRIX,
    FieldTypes.TEXT,
    FieldTypes.STATEMENT,
    FieldTypes.PAYMENT,
    FieldTypes.TABULAR_INPUT,
    FieldTypes.FILE_UPLOAD,
    FieldTypes.VIDEO_CONTENT,
    FieldTypes.IMAGE_CONTENT,
    'page_break',
    'hidden',
    'conditional'
]);

export const isCalculatedField = (field: StandardFormFieldDto | undefined | null): boolean => field?.type === FieldTypes.CALCULATED;

/** Does a respondent see this field? Not a calculation kept from them ("internal result"). */
export const isShownToRespondents = (field: StandardFormFieldDto | undefined | null): boolean => !(isCalculatedField(field) && field?.properties?.hiddenFromRespondents);

const isRepeatingGroupField = (field: StandardFormFieldDto): boolean => field?.type === FieldTypes.GROUP && !!field.properties?.repeat;

/** The fields on the pages of a page-based form. */
export function pageFields(slides: StandardFormFieldDto[] | undefined | null): StandardFormFieldDto[] {
    const list = slides ?? [];
    if (!list.length || list.some((slide) => slide?.type !== FieldTypes.SLIDE)) return [];
    return list.flatMap((slide) => slide?.properties?.fields ?? []).filter(Boolean);
}

export function getCalculatedFields(slides: StandardFormFieldDto[] | undefined | null): StandardFormFieldDto[] {
    return pageFields(slides).filter(isCalculatedField);
}

/** One variable a formula may read, with the label the formula shows. */
export interface CalculationVariable {
    key: string;
    label: string;
    kind: 'field' | 'group' | 'hidden' | 'calculated';
}

/** Plain text of a title (string or rich-text JSON; pipes left out). */
function titleText(title: unknown): string {
    if (typeof title === 'string') return title;
    if (!title || typeof title !== 'object') return '';
    const node = title as { type?: string; text?: string; content?: unknown[] };
    if (node.type === 'text' && typeof node.text === 'string') return node.text;
    return (node.content ?? []).map(titleText).join(node.type === 'doc' ? ' ' : '');
}

/** A field's own title as plain text ('' when untitled). */
export const fieldTitleText = (field: StandardFormFieldDto): string => (titleText(field.title) || (typeof field.value === 'string' ? field.value : '')).replace(/\s+/g, ' ').trim();

const fieldLabel = (field: StandardFormFieldDto): string => (titleText(field.title) || (typeof field.value === 'string' ? field.value : '')).replace(/\s+/g, ' ').trim() || field.id;

/** Every variable of the form, in form order (hidden fields last). */
export function calculationVariables(slides: StandardFormFieldDto[] | undefined | null, hiddenNames: string[] = []): CalculationVariable[] {
    const variables: CalculationVariable[] = [];
    pageFields(slides).forEach((field) => {
        if (!field?.id || field.internal) return;
        if (isRepeatingGroupField(field)) {
            const groupLabel = fieldLabel(field);
            (field.properties?.fields ?? []).forEach((child) => {
                if (child?.id && !child.internal) variables.push({ key: `${field.id}.${child.id}`, label: `${groupLabel}.${fieldLabel(child)}`, kind: 'group' });
            });
            return;
        }
        if (NOT_VARIABLE_TYPES.has(field.type) || field.type === FieldTypes.GROUP) return;
        variables.push({ key: field.id, label: fieldLabel(field), kind: isCalculatedField(field) ? 'calculated' : 'field' });
    });
    const fieldKeys = new Set(variables.map((variable) => variable.key));
    hiddenNames.forEach((name) => {
        if (name && !fieldKeys.has(name)) variables.push({ key: name, label: name, kind: 'hidden' });
    });
    return variables;
}

/**
 * Label ↔ key maps for the formula syntax: `{Label}` resolves to its key when
 * the label is unique, and a key can always be written as itself.
 */
export function formulaNames(variables: CalculationVariable[]) {
    const counts = new Map<string, number>();
    variables.forEach((variable) => counts.set(variable.label, (counts.get(variable.label) ?? 0) + 1));
    const byLabel = new Map<string, string>();
    const keys = new Set(variables.map((variable) => variable.key));
    variables.forEach((variable) => {
        if (counts.get(variable.label) === 1) byLabel.set(variable.label, variable.key);
    });
    // A shared label can't say which field it means: those print as their key.
    const labelOf = new Map(variables.filter((variable) => counts.get(variable.label) === 1).map((variable) => [variable.key, variable.label]));
    return {
        resolveField: (reference: string): string | null => byLabel.get(reference) ?? (keys.has(reference) ? reference : null),
        fieldLabel: (key: string): string => labelOf.get(key) ?? key
    };
}

/** The readable formula of an AST ('' when there is none or it is malformed). */
export function formulaText(expression: unknown, variables: CalculationVariable[]): string {
    if (expression === undefined || expression === null) return '';
    if (validateExpression(expression).length) return '';
    return printFormula(expression as ExprNode, { fieldLabel: formulaNames(variables).fieldLabel });
}

export interface FormulaParseResult {
    expression?: ExprNode;
    error?: { message: string; start: number; end: number };
}

/** Parse what the creator typed; '' clears the formula. */
export function parseFormulaText(text: string, variables: CalculationVariable[]): FormulaParseResult {
    if (!text.trim()) return { expression: undefined };
    try {
        return { expression: parseFormula(text, { resolveField: formulaNames(variables).resolveField }) };
    } catch (error) {
        if (error instanceof FormulaError) return { error: { message: error.message, start: error.start, end: error.end } };
        throw error;
    }
}

/** The variable keys an AST reads, in order of appearance. */
export function expressionVariables(ast: unknown): string[] {
    const found: string[] = [];
    const visit = (node: unknown) => {
        if (!node || typeof node !== 'object' || Array.isArray(node)) return;
        const entries = Object.entries(node as Record<string, unknown>);
        if (entries.length !== 1) return;
        const [op, value] = entries[0];
        if (op === 'var') {
            if (typeof value === 'string' && !found.includes(value)) found.push(value);
        } else if (Array.isArray(value)) value.forEach(visit);
    };
    visit(ast);
    return found;
}

/** Calculated fields ordered so each comes after the ones it reads; fields in a circle are left out. */
export function evaluationOrder(calcs: StandardFormFieldDto[]): StandardFormFieldDto[] {
    const byId = new Map(calcs.map((field) => [field.id, field]));
    const deps = new Map(calcs.map((field) => [field.id, expressionVariables(field.properties?.expression).filter((key) => byId.has(key))]));
    const done = new Set<string>();
    const ordered: StandardFormFieldDto[] = [];
    let progress = true;
    while (progress) {
        progress = false;
        byId.forEach((field, id) => {
            if (done.has(id) || deps.get(id)!.some((dep) => !done.has(dep))) return;
            done.add(id);
            ordered.push(field);
            progress = true;
        });
    }
    return ordered;
}

export interface CalculationProblem {
    fieldId: string;
    message: string;
    /** JSON pointer of the node inside the expression ('' = the whole formula). */
    path: string;
}

/** What a save would refuse: malformed formulas, unknown or internal fields, circles. */
export function calculationProblems(slides: StandardFormFieldDto[] | undefined | null, hiddenNames: string[] = []): CalculationProblem[] {
    const calcs = getCalculatedFields(slides);
    if (!calcs.length) return [];
    const variables = calculationVariables(slides, hiddenNames);
    const known = variables.map((variable) => variable.key);
    const problems: CalculationProblem[] = [];
    calcs.forEach((field) => {
        const expression = field.properties?.expression;
        if (expression === undefined || expression === null) return;
        const structural = validateExpression(expression);
        if (structural.length) {
            structural.forEach((problem) => problems.push({ fieldId: field.id, message: problem.message, path: problem.path }));
            return;
        }
        validateExpression(expression, { knownVariables: known }).forEach((problem) => problems.push({ fieldId: field.id, message: 'This formula uses a field that no longer exists or is internal.', path: problem.path }));
    });
    const ids = new Set(calcs.map((field) => field.id));
    if (evaluationOrder(calcs).length < calcs.length) {
        const ordered = new Set(evaluationOrder(calcs).map((field) => field.id));
        const circle = calcs.filter((field) => !ordered.has(field.id) && expressionVariables(field.properties?.expression).some((key) => ids.has(key)));
        const names = circle.map((f) => `'${fieldLabel(f)}'`).join(' → ');
        circle.forEach((field) => problems.push({ fieldId: field.id, message: `Calculations cannot depend on each other in a circle (${names}).`, path: '' }));
    }
    return problems;
}

// UUIDs: the ids the builder and AI give fields (hidden-field names are the creator's own words).
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/**
 * Builder hygiene after a question is deleted, made internal or a hidden
 * field removed: a formula reference that no longer reads anything becomes
 * `null`, which is what it evaluated to anyway (an unanswered value). Keeps
 * the form saveable. Without `hiddenNames`, only references that look like
 * field ids (UUIDs, group keys) and internal fields are swept. Mutates the
 * slides in place and returns them, like pruneOrphanedConditions.
 */
export function pruneOrphanedCalculationRefs(slides: StandardFormFieldDto[], hiddenNames?: string[]): StandardFormFieldDto[] {
    const calcs = getCalculatedFields(slides);
    if (!calcs.length) return slides;
    const known = new Set(calculationVariables(slides, hiddenNames ?? []).map((variable) => variable.key));
    const internal = new Set(
        pageFields(slides)
            .filter((field) => field.internal)
            .map((field) => field.id)
    );
    const orphan = (key: string) => !known.has(key) && (hiddenNames !== undefined || internal.has(key) || key.includes('.') || UUID.test(key));
    const sweep = (node: unknown): unknown => {
        if (!node || typeof node !== 'object' || Array.isArray(node)) return node;
        const entries = Object.entries(node as Record<string, unknown>);
        if (entries.length !== 1) return node;
        const [op, value] = entries[0];
        if (op === 'var') return typeof value === 'string' && orphan(value) ? null : node;
        return Array.isArray(value) ? { [op]: value.map(sweep) } : node;
    };
    calcs.forEach((field) => {
        const expression = field.properties?.expression;
        if (expression === undefined || expression === null || validateExpression(expression).length) return;
        if (!expressionVariables(expression).some(orphan)) return;
        field.properties = { ...field.properties, expression: sweep(expression) as ExprNode };
    });
    return slides;
}

/** The variables map of the answer-based keys (calculated values are added while evaluating). */
export function buildVariables(slides: StandardFormFieldDto[] | undefined | null, answers: Record<string, any>, hiddenValues: Record<string, string> = {}, hiddenNames?: string[]): Record<string, unknown> {
    const variables: Record<string, unknown> = {};
    Object.entries(hiddenValues ?? {}).forEach(([name, value]) => {
        if ((!hiddenNames || hiddenNames.includes(name)) && typeof value === 'string') variables[name] = value;
    });
    pageFields(slides).forEach((field) => {
        if (!field?.id || field.internal || isCalculatedField(field)) return;
        if (isRepeatingGroupField(field)) {
            const items = getGroupAnswerItems(answers?.[field.id]);
            (field.properties?.fields ?? []).forEach((child) => {
                if (!child?.id || child.internal) return;
                variables[`${field.id}.${child.id}`] = items.map((item) => getComparableAnswerValue(item?.[child.id], child.type) ?? null);
            });
            return;
        }
        if (NOT_VARIABLE_TYPES.has(field.type) || field.type === FieldTypes.GROUP) return;
        variables[field.id] = getComparableAnswerValue(answers?.[field.id], field.type) ?? null;
    });
    return variables;
}

/**
 * "Unanswered as 0": does an unanswered question (or an empty calculation)
 * this calculation reads count as 0? Its own setting, else on unless it
 * shows text. Group lists and hidden fields are always read as they are.
 * Shared cases with the server: docs/spec/calculated-fields.cases.json.
 */
export function unansweredAsZero(field: StandardFormFieldDto | undefined | null): boolean {
    const setting = field?.properties?.unansweredAsZero;
    if (setting !== undefined && setting !== null) return !!setting;
    return (field?.properties?.format?.style ?? 'number') !== 'text';
}

/** The variables a calculation reads: with "unanswered as 0", its empty question and calculation values become 0. */
export function readingFor(field: StandardFormFieldDto, variables: Record<string, unknown>, questions: Set<string>): Record<string, unknown> {
    if (!unansweredAsZero(field)) return variables;
    const reading = { ...variables };
    expressionVariables(field.properties?.expression).forEach((key) => {
        if (questions.has(key) && (reading[key] === undefined || reading[key] === null || reading[key] === '')) reading[key] = 0;
    });
    return reading;
}

/** Keys that read one question's answer or one calculation (what "unanswered as 0" applies to). */
export function questionKeys(slides: StandardFormFieldDto[] | undefined | null): Set<string> {
    const keys = new Set<string>();
    pageFields(slides).forEach((field) => {
        if (!field?.id || field.internal || NOT_VARIABLE_TYPES.has(field.type) || field.type === FieldTypes.GROUP) return;
        keys.add(field.id);
    });
    return keys;
}

/**
 * Has the respondent given any answer this calculation uses (directly or
 * through other calculations)? Until then the respondent page shows "Not
 * calculated yet" instead of, say, a 0% score. A formula that uses no
 * answers is always shown.
 */
export function usesAnyAnswer(field: StandardFormFieldDto, slides: StandardFormFieldDto[] | undefined | null, answers: Record<string, any>, hiddenValues: Record<string, string> = {}): boolean {
    const byId = new Map(pageFields(slides).map((f) => [f.id, f]));
    const seen = new Set<string>();
    const sources: string[] = [];
    const walk = (calc: StandardFormFieldDto) => {
        expressionVariables(calc.properties?.expression).forEach((key) => {
            if (seen.has(key)) return;
            seen.add(key);
            const source = byId.get(key);
            if (source && isCalculatedField(source)) walk(source);
            else sources.push(key);
        });
    };
    walk(field);
    if (!sources.length) return true;
    const filled = (value: unknown) => value !== undefined && value !== null && value !== '' && !(Array.isArray(value) && value.length === 0);
    return sources.some((key) => {
        const dot = key.indexOf('.');
        if (dot > 0) {
            const groupId = key.slice(0, dot);
            const child = byId.get(groupId)?.properties?.fields?.find((f) => f.id === key.slice(dot + 1));
            return !!child && getGroupAnswerItems(answers?.[groupId]).some((item) => filled(getComparableAnswerValue(item?.[child.id], child.type)));
        }
        const source = byId.get(key);
        if (source) return filled(getComparableAnswerValue(answers?.[key], source.type));
        return filled(hiddenValues?.[key]);
    });
}

/** Every calculated field's value (null when it has none), in dependency order. */
export function computeCalculatedValues(slides: StandardFormFieldDto[] | undefined | null, answers: Record<string, any>, hiddenValues: Record<string, string> = {}, today?: string, hiddenNames?: string[]): Record<string, ExprValue> {
    const calcs = getCalculatedFields(slides).filter((field) => field.id && !field.internal);
    if (!calcs.length) return {};
    const variables = buildVariables(slides, answers, hiddenValues, hiddenNames);
    const questions = questionKeys(slides);
    const values: Record<string, ExprValue> = {};
    calcs.forEach((field) => (values[field.id] = null));
    evaluationOrder(calcs).forEach((field) => {
        const expression = field.properties?.expression;
        let value: ExprValue = null;
        if (expression !== undefined && expression !== null) {
            const reading = readingFor(field, variables, questions);
            try {
                value = evaluateExpression(expression, reading, { today: today ?? null });
            } catch {
                value = null;
            }
        }
        variables[field.id] = value;
        values[field.id] = value;
    });
    return values;
}

/** The answer a calculated value is kept as (the server stores the same shape); undefined for no value. */
export function calculatedAnswer(value: ExprValue): Record<string, any> | undefined {
    if (typeof value === 'boolean') return { type: 'boolean', boolean: value };
    if (typeof value === 'number') return { type: 'number', number: value };
    if (typeof value === 'string') return value === '' ? undefined : { type: 'text', text: value };
    if (Array.isArray(value)) {
        const text = formatExpressionValue(value);
        return text ? { type: 'text', text } : undefined;
    }
    return undefined;
}

/** The stored value of a calculated answer (number, boolean or text), or null. */
export function calculatedAnswerValue(answer: any): ExprValue {
    if (!answer || typeof answer !== 'object') return null;
    if (typeof answer.number === 'number') return answer.number;
    if (typeof answer.boolean === 'boolean') return answer.boolean;
    if (typeof answer.text === 'string' && answer.text !== '') return answer.text;
    return null;
}

const sameAnswer = (a: any, b: any): boolean => JSON.stringify(a ?? null) === JSON.stringify(b ?? null);

/**
 * `answers` with every calculated field's answer set to its value now. The
 * same object when nothing changed (so a sync effect settles).
 */
export function withCalculatedAnswers(slides: StandardFormFieldDto[] | undefined | null, answers: Record<string, any>, hiddenValues: Record<string, string> = {}, today?: string, hiddenNames?: string[]): Record<string, any> {
    const values = computeCalculatedValues(slides, answers ?? {}, hiddenValues, today, hiddenNames);
    let next: Record<string, any> | null = null;
    Object.entries(values).forEach(([id, value]) => {
        const answer = calculatedAnswer(value);
        if (sameAnswer(answers?.[id], answer)) return;
        next = next ?? { ...(answers ?? {}) };
        if (answer) next[id] = answer;
        else delete next[id];
    });
    return next ?? answers;
}

/** The respondent's local date as YYYY-MM-DD (the `today()` of a formula). */
export function localToday(date: Date = new Date()): string {
    const pad = (n: number) => String(n).padStart(2, '0');
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

const intlLocale = (language?: string): string => (language && language.toLowerCase().startsWith('nl') ? 'nl-NL' : 'en-GB');

/**
 * A calculated value as respondents see it, per the field's format and the
 * form's language (EN/NL number formatting). '' for no value.
 */
export function formatCalculatedValue(value: ExprValue | undefined, format: CalculationFormat | undefined, language?: string): string {
    if (value === undefined || value === null) return '';
    const style = format?.style ?? 'number';
    if (typeof value !== 'number' || style === 'text') return formatExpressionValue(value);
    const decimals = format?.decimals;
    const fixed = typeof decimals === 'number' && decimals >= 0 && decimals <= CALCULATION_MAX_DECIMALS ? decimals : undefined;
    try {
        if (style === 'currency') {
            const digits = fixed ?? 2;
            return new Intl.NumberFormat(intlLocale(language), { style: 'currency', currency: format?.currency || DEFAULT_CURRENCY, minimumFractionDigits: digits, maximumFractionDigits: digits }).format(value);
        }
        if (style === 'percent') {
            const digits = fixed ?? 0;
            return new Intl.NumberFormat(intlLocale(language), { style: 'percent', minimumFractionDigits: digits, maximumFractionDigits: digits }).format(value);
        }
        return new Intl.NumberFormat(intlLocale(language), fixed === undefined ? { maximumFractionDigits: 15 } : { minimumFractionDigits: fixed, maximumFractionDigits: fixed }).format(value);
    } catch {
        return formatExpressionValue(value);
    }
}

/** Sample answers for the builder's live preview: a plausible value per question type. */
export function sampleVariables(variables: CalculationVariable[], slides: StandardFormFieldDto[] | undefined | null): Record<string, unknown> {
    const byId = new Map<string, StandardFormFieldDto>();
    pageFields(slides).forEach((field) => {
        byId.set(field.id, field);
        (field.properties?.fields ?? []).forEach((child) => byId.set(`${field.id}.${child.id}`, child));
    });
    const sample = (field: StandardFormFieldDto | undefined): unknown => {
        switch (field?.type) {
            case FieldTypes.NUMBER:
                return 10;
            case FieldTypes.RATING:
            case FieldTypes.LINEAR_RATING:
                return 4;
            case FieldTypes.YES_NO:
                return 'Yes';
            case FieldTypes.DATE:
                return localToday();
            case FieldTypes.MULTIPLE_CHOICE:
            case FieldTypes.DROP_DOWN: {
                const choice = field.properties?.choices?.[0]?.id ?? 'option';
                return field.properties?.allowMultipleSelection ? [choice] : choice;
            }
            default:
                return 'text';
        }
    };
    const out: Record<string, unknown> = {};
    variables.forEach((variable) => {
        if (variable.kind === 'calculated') return;
        if (variable.kind === 'hidden') out[variable.key] = 'value';
        else if (variable.kind === 'group') out[variable.key] = [sample(byId.get(variable.key)), sample(byId.get(variable.key))];
        else out[variable.key] = sample(byId.get(variable.key));
    });
    return out;
}
