// The form outline AI form creation shows for review before building
// (backend services/ai/outline.py). Edits here keep the outline buildable:
// deleting or moving a question drops the show/hide rules and jumps that no
// longer make sense, as the backend would on build.

export type OutlineQuestionType = 'short_text' | 'long_text' | 'email' | 'phone_number' | 'number' | 'url' | 'date' | 'yes_no' | 'multiple_choice' | 'dropdown' | 'rating' | 'linear_rating' | 'file_upload' | 'statement';

export interface OutlineValidation {
    minLength?: number;
    maxLength?: number;
    minValue?: number;
    maxValue?: number;
    preset?: 'digits' | 'letters' | 'alphanumeric';
}

export interface OutlineQuestion {
    key: string;
    label: string;
    type: OutlineQuestionType;
    required?: boolean;
    description?: string;
    whyWeAsk?: string;
    choices?: string[];
    allowMultiple?: boolean;
    validation?: OutlineValidation;
}

export interface OutlinePage {
    key: string;
    sectionTitle?: string;
    questions: OutlineQuestion[];
}

export interface OutlineCondition {
    question: string;
    comparison: string;
    value?: string;
}

export interface OutlineLogic {
    target: string;
    action: 'show' | 'hide';
    match: 'all' | 'any';
    conditions: OutlineCondition[];
}

export interface OutlineJump {
    fromPage: string;
    to: string;
    match: 'all' | 'any';
    conditions: OutlineCondition[];
}

export interface FormOutline {
    title: string;
    description?: string;
    language: string;
    theme?: string;
    pages: OutlinePage[];
    logic: OutlineLogic[];
    jumps: OutlineJump[];
    omitted?: { label: string; reason: string }[];
}

export const QUESTION_TYPE_LABELS: Record<OutlineQuestionType, string> = {
    short_text: 'Short text',
    long_text: 'Long text',
    email: 'Email',
    phone_number: 'Phone number',
    number: 'Number',
    url: 'Link',
    date: 'Date',
    yes_no: 'Yes / No',
    multiple_choice: 'Multiple choice',
    dropdown: 'Dropdown',
    rating: 'Rating',
    linear_rating: 'Scale',
    file_upload: 'File upload',
    statement: 'Statement'
};

export const CHOICE_TYPES: OutlineQuestionType[] = ['multiple_choice', 'dropdown'];
export const END = 'end';
export const LABEL_MAX = 500;
export const SECTION_TITLE_MAX = 120;
export const MAX_QUESTIONS_PER_PAGE = 15;

export function questionCount(outline: FormOutline): number {
    return outline.pages.reduce((sum, page) => sum + page.questions.length, 0);
}

function positions(outline: FormOutline): Map<string, [number, number]> {
    const map = new Map<string, [number, number]>();
    outline.pages.forEach((page, p) => page.questions.forEach((q, i) => map.set(q.key, [p, i])));
    return map;
}

function before(a: [number, number], b: [number, number]): boolean {
    return a[0] < b[0] || (a[0] === b[0] && a[1] < b[1]);
}

/** The outline without rules that no longer fit its questions and pages:
 * conditions on a missing or later question, jumps from or to a missing
 * page, or backwards. */
export function pruneRules(outline: FormOutline): FormOutline {
    const at = positions(outline);
    const pages = new Map(outline.pages.map((page, i) => [page.key, i]));
    const logic = outline.logic.filter((rule) => {
        const target = at.get(rule.target);
        return target !== undefined && rule.conditions.every((c) => at.has(c.question) && c.question !== rule.target && before(at.get(c.question)!, target));
    });
    const jumps = outline.jumps.filter((jump) => {
        const start = pages.get(jump.fromPage);
        if (start === undefined) return false;
        if (jump.to !== END) {
            const goal = pages.get(jump.to);
            if (goal === undefined || goal <= start) return false;
        }
        return jump.conditions.every((c) => at.has(c.question) && at.get(c.question)![0] <= start);
    });
    return { ...outline, logic, jumps };
}

function updatePage(outline: FormOutline, pageKey: string, change: (page: OutlinePage) => OutlinePage): FormOutline {
    return { ...outline, pages: outline.pages.map((page) => (page.key === pageKey ? change(page) : page)) };
}

function updateQuestion(outline: FormOutline, questionKey: string, change: (q: OutlineQuestion) => OutlineQuestion): FormOutline {
    return {
        ...outline,
        pages: outline.pages.map((page) => ({ ...page, questions: page.questions.map((q) => (q.key === questionKey ? change(q) : q)) }))
    };
}

export function renameQuestion(outline: FormOutline, key: string, label: string): FormOutline {
    return updateQuestion(outline, key, (q) => ({ ...q, label: label.slice(0, LABEL_MAX) }));
}

export function setRequired(outline: FormOutline, key: string, required: boolean): FormOutline {
    return updateQuestion(outline, key, (q) => ({ ...q, required }));
}

export function setChoices(outline: FormOutline, key: string, text: string): FormOutline {
    const choices = text
        .split('\n')
        .map((line) => line.trim())
        .filter(Boolean);
    return pruneRules(updateQuestion(outline, key, (q) => ({ ...q, choices })));
}

/** A new type keeps the label; what only fits the old type is dropped
 * (choices, validation), and so are rules that depended on its answers. */
export function changeType(outline: FormOutline, key: string, type: OutlineQuestionType): FormOutline {
    const changed = updateQuestion(outline, key, (q) => {
        const next: OutlineQuestion = { ...q, type };
        if (!CHOICE_TYPES.includes(type)) {
            delete next.choices;
            delete next.allowMultiple;
        }
        if (type !== q.type) delete next.validation;
        return next;
    });
    const dependsOn = (c: OutlineCondition) => c.question === key;
    return pruneRules({
        ...changed,
        logic: changed.logic.filter((rule) => !rule.conditions.some(dependsOn)),
        jumps: changed.jumps.filter((jump) => !jump.conditions.some(dependsOn))
    });
}

export function deleteQuestion(outline: FormOutline, key: string): FormOutline {
    return pruneRules({
        ...outline,
        pages: outline.pages.map((page) => ({ ...page, questions: page.questions.filter((q) => q.key !== key) }))
    });
}

/** Move a question one place up or down; past the edge of its page it
 * goes to the end of the previous page or the start of the next one. */
export function moveQuestion(outline: FormOutline, key: string, direction: -1 | 1): FormOutline {
    const at = positions(outline).get(key);
    if (!at) return outline;
    const [p, i] = at;
    const pages = outline.pages.map((page) => ({ ...page, questions: [...page.questions] }));
    const [question] = pages[p].questions.splice(i, 1);
    const target = i + direction;
    if (target >= 0 && target <= pages[p].questions.length) {
        pages[p].questions.splice(target, 0, question);
    } else if (direction < 0 && p > 0) {
        pages[p - 1].questions.push(question);
    } else if (direction > 0 && p < pages.length - 1) {
        pages[p + 1].questions.unshift(question);
    } else {
        return outline;
    }
    return pruneRules({ ...outline, pages });
}

export function canMove(outline: FormOutline, key: string, direction: -1 | 1): boolean {
    const at = positions(outline).get(key);
    if (!at) return false;
    const [p, i] = at;
    if (direction < 0) return i > 0 || p > 0;
    return i < outline.pages[p].questions.length - 1 || p < outline.pages.length - 1;
}

function freshKey(outline: FormOutline, prefix: string): string {
    const used = new Set<string>([...outline.pages.map((p) => p.key), ...outline.pages.flatMap((p) => p.questions.map((q) => q.key))]);
    let n = used.size + 1;
    while (used.has(`${prefix}${n}`)) n += 1;
    return `${prefix}${n}`;
}

export function addQuestion(outline: FormOutline, pageKey: string): { outline: FormOutline; key: string } {
    const key = freshKey(outline, 'new');
    const next = updatePage(outline, pageKey, (page) => ({
        ...page,
        questions: [...page.questions, { key, label: '', type: 'short_text', required: false }]
    }));
    return { outline: next, key };
}

export function setSectionTitle(outline: FormOutline, pageKey: string, title: string): FormOutline {
    return updatePage(outline, pageKey, (page) => ({ ...page, sectionTitle: title.slice(0, SECTION_TITLE_MAX) }));
}

/** What still has to be fixed before building (shown to the person). */
export function outlineProblems(outline: FormOutline): string[] {
    const problems: string[] = [];
    if (!outline.title.trim()) problems.push('Give the form a title.');
    if (questionCount(outline) === 0) problems.push('Add at least one question.');
    outline.pages.forEach((page, p) => {
        if (page.questions.length > MAX_QUESTIONS_PER_PAGE) problems.push(`Page ${p + 1} has more than ${MAX_QUESTIONS_PER_PAGE} questions.`);
        page.questions.forEach((q, i) => {
            if (!q.label.trim()) problems.push(`Page ${p + 1}, question ${i + 1} has no text.`);
        });
    });
    return problems;
}

/** The outline as the build endpoint takes it: trimmed text, no empty
 * optional values. */
export function outlineForBuild(outline: FormOutline): FormOutline {
    const pruned = pruneRules(outline);
    return {
        ...pruned,
        title: pruned.title.trim(),
        pages: pruned.pages.map((page) => ({
            ...page,
            sectionTitle: page.sectionTitle?.trim() || undefined,
            questions: page.questions.map((q) => ({ ...q, label: q.label.trim() }))
        }))
    };
}
