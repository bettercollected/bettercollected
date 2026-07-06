import { JSONContent } from '@tiptap/react';

import { StandardFormFieldDto, V2InputFields } from '@app/models/dtos/form';
import { getComparableAnswerValue } from '@app/utils/conditional-logic';

/**
 * Answer piping ("recall") — reference an earlier answer or a hidden field
 * (URL parameter) inside later question text: "Thanks, {name}!".
 *
 * Two storage forms, one resolver:
 *  - Field TITLES are TipTap JSON; a pipe is an inline atom node
 *    (`answerPipe`, see utils/richTextEditorExtenstion/answer-pipe.ts) with
 *    attrs {kind, pipeKey, label, fallback}. The builder inserts these as
 *    chips; the responder runtime replaces them with resolved text before the
 *    JSON is turned into HTML.
 *  - DESCRIPTIONS and thank-you messages are plain strings; a pipe is the
 *    text token `{{field:<fieldId>}}` / `{{hidden:<name>}}`, with an optional
 *    `|fallback`: `{{hidden:name|there}}`.
 *
 * Values come from the same `getComparableAnswerValue` the conditional-logic
 * evaluator uses, so piping and logic can never disagree about an answer.
 * Hidden-field values are the URL parameters captured when the form loaded.
 */

export type PipeKind = 'field' | 'hidden';

export const ANSWER_PIPE_NODE = 'answerPipe';

export interface PipeContext {
    /** The form's slides (`form.fields`), used to look up a field's type. */
    slides?: Array<StandardFormFieldDto>;
    /** In-progress responder answers, keyed by field id. */
    answers?: Record<string, any>;
    /** Captured hidden-field (URL parameter) values, keyed by declared name. */
    hiddenValues?: Record<string, string>;
}

/** Flatten slides into an id → field map for answerable fields. */
export function getInputFieldsById(slides?: Array<StandardFormFieldDto>): Record<string, StandardFormFieldDto> {
    const byId: Record<string, StandardFormFieldDto> = {};
    (slides ?? []).forEach((slide) => {
        slide?.properties?.fields?.forEach((field) => {
            if (field?.id) byId[field.id] = field;
        });
    });
    return byId;
}

/** Render a comparable answer value as display text. Empty-ish → undefined. */
function formatPipeValue(value: any): string | undefined {
    if (value === undefined || value === null) return undefined;
    if (Array.isArray(value)) {
        const parts = value.map((v) => String(v)).filter((v) => v !== '');
        return parts.length ? parts.join(', ') : undefined;
    }
    const text = String(value);
    return text === '' ? undefined : text;
}

/** Resolve one pipe to display text, or undefined when there's no value yet. */
export function resolvePipeValue(kind: PipeKind | string, pipeKey: string, context: PipeContext): string | undefined {
    if (!pipeKey) return undefined;
    if (kind === 'hidden') {
        return formatPipeValue(context.hiddenValues?.[pipeKey]);
    }
    const field = getInputFieldsById(context.slides)[pipeKey];
    if (!field) return undefined;
    return formatPipeValue(getComparableAnswerValue(context.answers?.[pipeKey], field.type));
}

// `{{field:<id>}}` / `{{hidden:<name>|fallback}}` — key stops at `|` or `}`.
const TEXT_PIPE_PATTERN = /\{\{\s*(field|hidden)\s*:\s*([^}|]+?)\s*(?:\|([^}]*))?\}\}/g;

/** Resolve text-token pipes in a plain string (descriptions, thank-you text). */
export function resolvePipesInText(text: string | null | undefined, context: PipeContext): string | null | undefined {
    if (!text || typeof text !== 'string') return text;
    return text.replace(TEXT_PIPE_PATTERN, (_match, kind, key, fallback) => {
        return resolvePipeValue(kind, key.trim(), context) ?? (fallback ?? '').trim();
    });
}

function resolveNode(node: JSONContent, context: PipeContext): JSONContent | null {
    if (node?.type === ANSWER_PIPE_NODE) {
        const attrs = node.attrs ?? {};
        const value = resolvePipeValue(attrs.kind, attrs.pipeKey, context) ?? (attrs.fallback || '');
        // TipTap text nodes must be non-empty — drop the node entirely when
        // there's nothing to show.
        if (!value) return null;
        const textNode: JSONContent = { type: 'text', text: value };
        if (node.marks?.length) textNode.marks = node.marks;
        return textNode;
    }
    if (!node?.content?.length) return node;
    return {
        ...node,
        content: node.content.map((child) => resolveNode(child, context)).filter((child): child is JSONContent => child !== null)
    };
}

/**
 * Resolve pipes in a field title (TipTap JSON or legacy plain string).
 * Returns the same shape it was given; the input is never mutated.
 */
export function resolvePipesInTitle(title: JSONContent | string | undefined, context: PipeContext): JSONContent | string | undefined {
    if (!title) return title;
    if (typeof title === 'string') return resolvePipesInText(title, context) ?? title;
    return resolveNode(title, context) ?? title;
}

/** Does a title contain any pipe nodes? (Cheap check to skip resolution.) */
export function titleHasPipes(title: JSONContent | string | undefined): boolean {
    if (!title) return false;
    if (typeof title === 'string') {
        TEXT_PIPE_PATTERN.lastIndex = 0;
        return TEXT_PIPE_PATTERN.test(title);
    }
    if (title.type === ANSWER_PIPE_NODE) return true;
    return (title.content ?? []).some((child) => titleHasPipes(child));
}

/**
 * Remove pipe nodes that reference deleted fields or undeclared hidden fields
 * (builder-side hygiene, the piping counterpart of `pruneOrphanedConditions`).
 * Mutates field titles in place, like the conditions pruner does.
 */
export function pruneOrphanedPipes(slides: Array<StandardFormFieldDto>, hiddenFieldNames?: string[]): Array<StandardFormFieldDto> {
    const fieldIds = new Set<string>();
    slides.forEach((slide) => slide?.properties?.fields?.forEach((f) => fieldIds.add(f.id)));
    const hiddenNames = hiddenFieldNames ? new Set(hiddenFieldNames) : null;

    const isOrphan = (node: JSONContent): boolean => {
        if (node?.type !== ANSWER_PIPE_NODE) return false;
        const attrs = node.attrs ?? {};
        if (attrs.kind === 'hidden') return hiddenNames !== null && !hiddenNames.has(attrs.pipeKey);
        return !fieldIds.has(attrs.pipeKey);
    };

    const pruneNode = (node: JSONContent): void => {
        if (!node?.content?.length) return;
        node.content = node.content.filter((child) => !isOrphan(child));
        node.content.forEach(pruneNode);
    };

    slides.forEach((slide) => {
        slide?.properties?.fields?.forEach((field) => {
            if (field?.title && typeof field.title !== 'string') pruneNode(field.title);
        });
    });

    return slides;
}

/**
 * Pick the declared hidden-field values out of a share link's query string.
 * Only declared names are captured — arbitrary URL parameters are never stored.
 */
export function captureHiddenFieldValues(declaredNames: string[] | undefined, search: string | URLSearchParams): Record<string, string> {
    const params = typeof search === 'string' ? new URLSearchParams(search) : search;
    const captured: Record<string, string> = {};
    (declaredNames ?? []).forEach((name) => {
        const value = params.get(name);
        if (value !== null && value !== '') captured[name] = value;
    });
    return captured;
}

/**
 * URL prefill for visible input fields: `?field_<fieldId>=value`.
 * Returns {fieldId, field, value} for every param that addresses a real
 * answerable field; the caller applies them with the typed answer setters.
 */
export function getPrefillEntries(slides: Array<StandardFormFieldDto> | undefined, search: string | URLSearchParams): Array<{ field: StandardFormFieldDto; value: string }> {
    const params = typeof search === 'string' ? new URLSearchParams(search) : search;
    const byId = getInputFieldsById(slides);
    const entries: Array<{ field: StandardFormFieldDto; value: string }> = [];
    params.forEach((value, key) => {
        if (!key.startsWith('field_') || value === '') return;
        const field = byId[key.slice('field_'.length)];
        if (field && V2InputFields.includes(field.type)) entries.push({ field, value });
    });
    return entries;
}
