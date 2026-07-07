import { mergeAttributes, Node } from '@tiptap/core';

/**
 * Inline atom node for answer piping — a chip inside a field title that
 * stands for "the answer to an earlier question" (kind: 'field') or "a hidden
 * URL parameter" (kind: 'hidden'). Stored in the title's TipTap JSON as
 * {type: 'answerPipe', attrs: {kind, pipeKey, label, fallback}}.
 *
 * The builder renders the chip; the responder runtime never renders this node
 * — `resolvePipesInTitle` (utils/answer-piping.ts) replaces it with the
 * resolved answer text before the JSON becomes HTML.
 *
 * The DOM round-trip matters: the builder feeds the editor HTML generated
 * from the stored JSON, so parseHTML/renderHTML must preserve every attr.
 */
export const AnswerPipe = Node.create({
    name: 'answerPipe',
    group: 'inline',
    inline: true,
    atom: true,
    selectable: true,

    addAttributes() {
        return {
            kind: {
                default: 'field',
                parseHTML: (element) => element.getAttribute('data-pipe-kind') || 'field'
            },
            pipeKey: {
                default: '',
                parseHTML: (element) => element.getAttribute('data-pipe-key') || ''
            },
            label: {
                default: '',
                parseHTML: (element) => element.getAttribute('data-pipe-label') || ''
            },
            fallback: {
                default: '',
                parseHTML: (element) => element.getAttribute('data-pipe-fallback') || ''
            }
        };
    },

    parseHTML() {
        return [{ tag: 'span[data-pipe-key]' }];
    },

    renderHTML({ node, HTMLAttributes }) {
        return [
            'span',
            mergeAttributes(HTMLAttributes, {
                'data-pipe-kind': node.attrs.kind,
                'data-pipe-key': node.attrs.pipeKey,
                'data-pipe-label': node.attrs.label,
                'data-pipe-fallback': node.attrs.fallback,
                class: 'answer-pipe-chip'
            }),
            `@${node.attrs.label || node.attrs.pipeKey}`
        ];
    }
});
