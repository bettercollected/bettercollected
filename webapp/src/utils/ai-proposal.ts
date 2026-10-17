import { StandardFormFieldDto } from '@app/models/dtos/form';
import { extractTextfromJSON } from '@app/utils/richTextEditorExtenstion/get-html-from-json';

/**
 * AI chat proposals (backend services/ai/proposals.py): what the assistant
 * would change, before anything is saved. The change list is built here from
 * the proposal's form spec diffs, one per op, so each line can be accepted
 * or left out (by its op).
 */

export interface DiffChange {
    path: string;
    before?: any;
    after?: any;
}

interface DiffItem {
    id: string;
    path: string;
}

export interface DiffSection {
    added: DiffItem[];
    removed: DiffItem[];
    moved: Array<{ id: string; from: string; to: string }>;
    changed: Array<{ id: string; path: string; changes: DiffChange[] }>;
}

export interface SpecDiff {
    form?: DiffChange[];
    pages?: DiffSection;
    fields?: DiffSection;
    changed?: boolean;
}

export interface ProposalOpResult {
    index: number;
    op: string;
    ok: boolean;
    message: string;
}

export interface ProposalStep {
    index: number;
    diff: SpecDiff;
    requires?: number[];
}

export interface AIProposal {
    id: string;
    ops: any[];
    form: any;
    diff: SpecDiff;
    results: ProposalOpResult[];
    summary: string;
    steps?: ProposalStep[];
    expiresAt?: string;
}

export type ChangeKind = 'added' | 'removed' | 'moved' | 'changed';

export interface ProposalChange {
    key: string;
    opIndex: number;
    text: string;
    kind: ChangeKind;
    fieldId?: string;
    pageId?: string;
}

export interface ProposalChangeGroup {
    key: string;
    label: string;
    pageId?: string;
    changes: ProposalChange[];
}

const PAGE_IN_PATH = /^\/pages\/(\d+)/;

function pageIndexOf(path: string): number | null {
    const match = PAGE_IN_PATH.exec(path ?? '');
    return match ? Number(match[1]) : null;
}

function slides(form: any): StandardFormFieldDto[] {
    return ((form?.fields ?? []) as StandardFormFieldDto[]).filter((field) => field?.type === 'slide');
}

function findField(form: any, id: string): StandardFormFieldDto | null {
    for (const slide of slides(form)) {
        for (const field of slide.properties?.fields ?? []) {
            if (field.id === id) return field;
            for (const child of field.properties?.fields ?? []) if (child.id === id) return child;
        }
    }
    return null;
}

function shorten(text: string, max = 60): string {
    const plain = (text ?? '').replace(/\s+/g, ' ').trim();
    return plain.length > max ? `${plain.slice(0, max - 1)}…` : plain;
}

function fieldName(form: any, id: string): string {
    const field = findField(form, id);
    return field ? shorten(extractTextfromJSON(field)) : 'a question';
}

function plain(value: any): string {
    if (value === null || value === undefined) return '';
    if (typeof value === 'string') return shorten(value);
    if (typeof value === 'object') return shorten(extractTextfromJSON({ title: value } as StandardFormFieldDto));
    return String(value);
}

function humanize(key: string): string {
    return key
        .replace(/([a-z])([A-Z])/g, '$1 $2')
        .replace(/_/g, ' ')
        .toLowerCase();
}

function capitalize(text: string): string {
    return text ? text.charAt(0).toUpperCase() + text.slice(1) : text;
}

/** The part of ``path`` below ``prefix``, as segments. */
function below(path: string, prefix: string): string[] {
    return path.slice(prefix.length).split('/').filter(Boolean);
}

function fieldChangeText(key: string[], change: DiffChange, name: string): string {
    switch (key[0]) {
        case 'title':
            return change.after ? `Question '${name}': '${plain(change.after)}'` : `Removed the text of '${name}'`;
        case 'validations':
            if (key[1] === 'required') return change.after ? `Made '${name}' required` : `Made '${name}' optional`;
            return `Changed what counts as a valid answer to '${name}'`;
        case 'choices':
            return `Changed the options of '${name}'`;
        case 'logic':
            return `Changed when '${name}' is shown`;
        case 'description':
            return `Changed the description of '${name}'`;
        case 'internal':
            return change.after ? `Made '${name}' staff only` : `Showed '${name}' to respondents`;
        case 'type':
            return `Changed '${name}' to a ${humanize(String(change.after ?? 'other'))} question`;
        default:
            return `Changed the ${humanize(key[0] ?? 'settings')} of '${name}'`;
    }
}

function pageChangeText(key: string[], change: DiffChange, number: number): string {
    switch (key[0]) {
        case 'sectionTitle':
            return change.after ? `Section title of page ${number}: '${plain(change.after)}'` : `Removed the section title of page ${number}`;
        case 'jumps':
            return `Changed where page ${number} leads`;
        case 'layout':
            return `Changed the layout of page ${number}`;
        case 'theme':
            return `Changed the look of page ${number}`;
        case 'showQuestionNumbers':
            return `Turned question numbers ${change.after ? 'on' : 'off'} on page ${number}`;
        default:
            return `Changed the ${humanize(key[0] ?? 'settings')} of page ${number}`;
    }
}

type GroupKey = { key: string; label: string; pageId?: string; order: number };

const FORM_GROUP: GroupKey = { key: 'form', label: 'Form and theme', order: 0 };
const WELCOME_GROUP: GroupKey = { key: 'welcome', label: 'Welcome page', order: 1 };
const ENDING_GROUP: GroupKey = { key: 'ending', label: 'Ending', order: 100000 };
const SETTINGS_GROUP: GroupKey = { key: 'settings', label: 'Privacy and settings', order: 100001 };
const OTHER_GROUP: GroupKey = { key: 'other', label: 'Other changes', order: 100002 };

function pageGroup(form: any, index: number): GroupKey {
    const page = slides(form)[index];
    return { key: `page:${page?.id ?? index}`, label: `Page ${index + 1}`, pageId: page?.id, order: 10 + index };
}

function formChangeLines(changes: DiffChange[]): Array<{ group: GroupKey; text: string }> {
    const lines: Array<{ group: GroupKey; text: string }> = [];
    let themeColours = false;
    for (const change of changes) {
        const [top, sub] = change.path.split('/').filter(Boolean);
        if (top === 'title') lines.push({ group: FORM_GROUP, text: change.after ? `Renamed the form to '${plain(change.after)}'` : 'Removed the form title' });
        else if (top === 'description') lines.push({ group: FORM_GROUP, text: 'Changed the form description' });
        else if (top === 'theme') {
            if (sub === 'title' && change.after) lines.push({ group: FORM_GROUP, text: `Changed theme to ${plain(change.after)}` });
            else if (sub === 'style' && change.after) lines.push({ group: FORM_GROUP, text: `Changed style to ${capitalize(plain(change.after))}` });
            else themeColours = true;
        } else if (top === 'welcomePage') {
            if (sub === 'title' && change.after) lines.push({ group: WELCOME_GROUP, text: `Welcome title: '${plain(change.after)}'` });
            else lines.push({ group: WELCOME_GROUP, text: `Changed the welcome page ${humanize(sub ?? 'content')}` });
        } else if (top === 'endings') lines.push({ group: ENDING_GROUP, text: 'Changed the ending' });
        else if (top === 'trust') {
            if (sub === 'purpose') lines.push({ group: SETTINGS_GROUP, text: change.after ? `Purpose: '${plain(change.after)}'` : 'Removed the purpose' });
            else lines.push({ group: SETTINGS_GROUP, text: `Changed the ${humanize(sub ?? 'privacy settings')}` });
        } else if (top === 'hiddenFields') lines.push({ group: SETTINGS_GROUP, text: 'Changed the hidden fields' });
        else if (top === 'logo') lines.push({ group: FORM_GROUP, text: 'Changed the logo settings' });
        else lines.push({ group: FORM_GROUP, text: `Changed the ${humanize(top ?? 'form')}` });
    }
    // Colours, background and the like: one line, after a named theme if any.
    if (themeColours && !lines.some((line) => line.text.startsWith('Changed theme to'))) lines.push({ group: FORM_GROUP, text: 'Changed the theme colours' });
    return lines;
}

interface Line {
    group: GroupKey;
    text: string;
    kind: ChangeKind;
    fieldId?: string;
    pageId?: string;
}

function stepLines(diff: SpecDiff, before: any, after: any): Line[] {
    const lines: Line[] = [];
    for (const line of formChangeLines(diff.form ?? [])) lines.push({ ...line, kind: 'changed' });

    const pages = diff.pages;
    for (const item of pages?.added ?? []) {
        const index = pageIndexOf(item.path) ?? 0;
        lines.push({ group: pageGroup(after, index), text: `Added page ${index + 1}`, kind: 'added', pageId: item.id });
    }
    for (const item of pages?.removed ?? []) {
        const index = pageIndexOf(item.path) ?? 0;
        lines.push({ group: { ...pageGroup(before, index), label: `Page ${index + 1} (removed)` }, text: `Removed page ${index + 1}`, kind: 'removed', pageId: item.id });
    }
    for (const item of pages?.moved ?? []) {
        const from = (pageIndexOf(item.from) ?? 0) + 1;
        const to = pageIndexOf(item.to) ?? 0;
        lines.push({ group: pageGroup(after, to), text: `Moved page ${from} to position ${to + 1}`, kind: 'moved', pageId: item.id });
    }
    for (const item of pages?.changed ?? []) {
        const index = pageIndexOf(item.path) ?? 0;
        const seen = new Set<string>();
        for (const change of item.changes) {
            const text = pageChangeText(below(change.path, item.path), change, index + 1);
            if (seen.has(text)) continue;
            seen.add(text);
            lines.push({ group: pageGroup(after, index), text, kind: 'changed', pageId: item.id });
        }
    }

    const fields = diff.fields;
    for (const item of fields?.added ?? []) {
        const index = pageIndexOf(item.path) ?? 0;
        const field = findField(after, item.id);
        const what = field?.type === 'text' ? 'text' : 'question';
        const group = pageGroup(after, index);
        lines.push({ group, text: `Added ${what} '${fieldName(after, item.id)}' on page ${index + 1}`, kind: 'added', fieldId: item.id, pageId: group.pageId });
    }
    for (const item of fields?.removed ?? []) {
        const index = pageIndexOf(item.path) ?? 0;
        const group = pageGroup(before, index);
        lines.push({ group, text: `Removed question '${fieldName(before, item.id)}' from page ${index + 1}`, kind: 'removed', fieldId: item.id, pageId: group.pageId });
    }
    for (const item of fields?.moved ?? []) {
        const from = pageIndexOf(item.from) ?? 0;
        const to = pageIndexOf(item.to) ?? 0;
        const group = pageGroup(after, to);
        const text = from === to ? `Moved question '${fieldName(after, item.id)}' within page ${to + 1}` : `Moved question '${fieldName(after, item.id)}' to page ${to + 1}`;
        lines.push({ group, text, kind: 'moved', fieldId: item.id, pageId: group.pageId });
    }
    for (const item of fields?.changed ?? []) {
        const index = pageIndexOf(item.path) ?? 0;
        const group = pageGroup(after, index);
        // Named as it was: "Question 'Your name': 'Full name'".
        const name = fieldName(before, item.id);
        const seen = new Set<string>();
        for (const change of item.changes) {
            const text = fieldChangeText(below(change.path, item.path), change, name);
            if (seen.has(text)) continue;
            seen.add(text);
            lines.push({ group, text, kind: 'changed', fieldId: item.id, pageId: group.pageId });
        }
    }
    return lines;
}

/**
 * The proposal as a readable change list grouped by page: every line knows
 * the op that makes it. ``before`` is the form as the editor shows it now.
 * An op that changes nothing visible still gets a line (its result message),
 * so each op can be chosen.
 */
export function buildProposalChanges(proposal: AIProposal, before: any): ProposalChangeGroup[] {
    const groups = new Map<string, { group: GroupKey; changes: ProposalChange[] }>();
    const add = (group: GroupKey, change: ProposalChange) => {
        const entry = groups.get(group.key) ?? { group, changes: [] };
        entry.changes.push(change);
        groups.set(group.key, entry);
    };
    const stepsByOp = new Map((proposal.steps ?? []).map((step) => [step.index, step]));
    for (const result of proposal.results ?? []) {
        if (!result.ok) continue;
        const step = stepsByOp.get(result.index);
        const lines = step ? stepLines(step.diff ?? {}, before, proposal.form) : [];
        if (!lines.length) {
            add(OTHER_GROUP, { key: `${result.index}:0`, opIndex: result.index, text: result.message, kind: 'changed' });
            continue;
        }
        lines.forEach((line, i) => add(line.group, { key: `${result.index}:${i}`, opIndex: result.index, text: line.text, kind: line.kind, fieldId: line.fieldId, pageId: line.pageId }));
    }
    return Array.from(groups.values())
        .sort((a, b) => a.group.order - b.group.order)
        .map(({ group, changes }) => ({ key: group.key, label: group.label, pageId: group.pageId, changes }));
}

/** The ops a proposal can accept: those that worked when proposed. */
export function acceptableOps(proposal: AIProposal): number[] {
    return (proposal.results ?? []).filter((result) => result.ok).map((result) => result.index);
}

function requiresMap(proposal: AIProposal): Map<number, number[]> {
    return new Map((proposal.steps ?? []).map((step) => [step.index, step.requires ?? []]));
}

/**
 * Check or uncheck an op, keeping the choice acceptable: an op comes with
 * the ops whose refs it uses, and leaving one out leaves out what builds on it.
 */
export function toggleOp(proposal: AIProposal, selected: number[], opIndex: number, checked: boolean): number[] {
    const requires = requiresMap(proposal);
    const next = new Set(selected);
    if (checked) {
        const stack = [opIndex];
        while (stack.length) {
            const op = stack.pop()!;
            if (next.has(op) && op !== opIndex) continue;
            next.add(op);
            stack.push(...(requires.get(op) ?? []).filter((dep) => !next.has(dep)));
        }
    } else {
        const stack = [opIndex];
        while (stack.length) {
            const op = stack.pop()!;
            next.delete(op);
            requires.forEach((deps, dependent) => {
                if (deps.includes(op) && next.has(dependent)) stack.push(dependent);
            });
        }
    }
    return Array.from(next).sort((a, b) => a - b);
}

export type FieldHighlight = 'added' | 'changed';

export interface ProposalHighlights {
    fields: Record<string, FieldHighlight>;
    /** Changed lines per page id. */
    pages: Record<string, number>;
}

/** What the canvas and the page rail mark while a proposal is open. */
export function proposalHighlights(groups: ProposalChangeGroup[]): ProposalHighlights {
    const highlights: ProposalHighlights = { fields: {}, pages: {} };
    for (const group of groups) {
        for (const change of group.changes) {
            if (change.fieldId && change.kind !== 'removed') {
                highlights.fields[change.fieldId] = change.kind === 'added' || highlights.fields[change.fieldId] === 'added' ? 'added' : 'changed';
            }
            if (change.pageId) highlights.pages[change.pageId] = (highlights.pages[change.pageId] ?? 0) + 1;
        }
    }
    return highlights;
}
