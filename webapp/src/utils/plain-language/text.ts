/**
 * Plain-text input for the plain-language check.
 *
 * Question titles are TipTap JSON (or a legacy plain string); descriptions are
 * plain strings that may carry `{{field:…}}` / `{{hidden:…}}` pipe tokens.
 * Every pipe — an `answerPipe` chip, a `{{…}}` token or a bare `@name`
 * mention — becomes one PIPE placeholder: it still counts as one word for
 * sentence length (the responder sees one answer there), but it is neither a
 * letter nor a digit, so no rule can match it as a word.
 */

/** Unicode private-use character standing in for a piped value. */
export const PIPE = '\uE000';

const TEXT_PIPE_TOKEN = /\{\{[^{}]*\}\}/g;
// `@name` as typed or as a chip renders it; not an e-mail address (`a@b.nl`).
const AT_MENTION = /(^|[^\p{L}\p{N}._%+-])@[\p{L}\p{N}_][\p{L}\p{N}_.·-]*/gu;

/** Replace pipe tokens in plain text with the PIPE placeholder. */
export function maskPipeTokens(text: string): string {
    return text.replace(TEXT_PIPE_TOKEN, PIPE).replace(AT_MENTION, (_match, before) => `${before}${PIPE}`);
}

interface RichNode {
    type?: string;
    text?: string;
    content?: RichNode[];
}

const BLOCK_NODES = new Set(['paragraph', 'heading', 'listItem', 'blockquote', 'hardBreak']);

function walk(node: RichNode | undefined | null): string {
    if (!node) return '';
    if (node.type === 'text') return node.text ?? '';
    if (node.type === 'answerPipe') return PIPE;
    if (node.type === 'hardBreak') return '\n';
    const inner = (node.content ?? []).map(walk).join('');
    // Blocks are separate lines: a sentence never runs across two paragraphs.
    return BLOCK_NODES.has(node.type ?? '') ? `${inner}\n` : inner;
}

/**
 * The text a responder reads for a title or description, with pipes masked.
 * Accepts TipTap JSON, a JSON-encoded string of it, or plain text.
 */
export function plainTextForCheck(value: unknown): string {
    if (value === null || value === undefined) return '';
    if (typeof value === 'string') {
        const trimmed = value.trim();
        if (trimmed.startsWith('{') && trimmed.includes('"type"')) {
            try {
                return plainTextForCheck(JSON.parse(trimmed));
            } catch {
                // Not JSON after all: treat as plain text below.
            }
        }
        return maskPipeTokens(value).trim();
    }
    if (typeof value === 'object') return maskPipeTokens(walk(value as RichNode)).trim();
    return '';
}

/** Words, counting a pipe as one word. Hyphenated and apostrophe words stay whole. */
export function tokenize(text: string): string[] {
    return text.match(/[\p{L}\p{N}\uE000](?:[\p{L}\p{N}\p{M}\uE000]|['’-](?=[\p{L}\p{N}]))*/gu) ?? [];
}

/**
 * Sentences: split after . ! ? … and at line breaks. Abbreviations ("bijv.",
 * "e.g.") split early, which only ever shortens a sentence — the safe side.
 */
export function splitSentences(text: string): string[] {
    return text
        .split(/(?<=[.!?…])\s+|\n+/u)
        .map((sentence) => sentence.trim())
        .filter(Boolean);
}

/**
 * Clauses for the passive rule: a participle belongs to its own clause, so
 * "U kunt ons bellen, het formulier is ingevuld" only looks inside each part.
 */
export function splitClauses(sentence: string): string[] {
    return sentence
        .split(/[,;:()?!.–—]+/u)
        .map((clause) => clause.trim())
        .filter(Boolean);
}
