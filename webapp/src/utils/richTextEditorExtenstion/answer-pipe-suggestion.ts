import { Extension } from '@tiptap/core';
import Suggestion, { SuggestionKeyDownProps, SuggestionProps } from '@tiptap/suggestion';

/**
 * Typing `@` in a title opens an inline picker of pipeable values (earlier
 * answers + hidden fields) at the caret — the UX people know from mentions.
 * Selecting an item replaces the typed `@query` with an answerPipe node
 * (see answer-pipe.ts). The "@ Answer" toolbar button remains as the
 * discoverable entry point; both insert the same node.
 */

export interface PipeSuggestionItem {
    kind: 'field' | 'hidden';
    pipeKey: string;
    label: string;
    /** Section header the item renders under. */
    group: 'Answers' | 'Hidden fields';
}

/** Case-insensitive filter of pipeable items against the typed query. */
export function filterPipeSuggestionItems(items: PipeSuggestionItem[], query: string): PipeSuggestionItem[] {
    const needle = query.trim().toLowerCase();
    if (!needle) return items;
    return items.filter((item) => item.label.toLowerCase().includes(needle));
}

/** The floating list itself — plain DOM so it can follow the caret rect. */
class PipeSuggestionList {
    private container: HTMLDivElement;
    private items: PipeSuggestionItem[] = [];
    private selectedIndex = 0;
    private command: (item: PipeSuggestionItem) => void = () => undefined;

    constructor() {
        this.container = document.createElement('div');
        this.container.className = 'answer-pipe-suggestions fixed z-[9999] max-h-64 w-72 overflow-auto rounded-lg border bg-white py-1 shadow-lg';
        this.container.style.display = 'none';
        document.body.appendChild(this.container);
    }

    update(props: SuggestionProps<PipeSuggestionItem>) {
        this.items = props.items;
        this.command = (item) => props.command(item);
        this.selectedIndex = 0;
        this.renderItems();
        this.position(props.clientRect?.());
    }

    private position(rect?: DOMRect | null) {
        if (!rect) return;
        this.container.style.display = this.items.length ? 'block' : 'none';
        // Below the caret; flip above when there's no room.
        const height = Math.min(this.container.scrollHeight, 256);
        const top = rect.bottom + height > window.innerHeight ? rect.top - height - 4 : rect.bottom + 4;
        this.container.style.top = `${top}px`;
        this.container.style.left = `${Math.min(rect.left, window.innerWidth - 296)}px`;
    }

    private renderItems() {
        this.container.innerHTML = '';
        let lastGroup: string | null = null;
        this.items.forEach((item, index) => {
            if (item.group !== lastGroup) {
                lastGroup = item.group;
                const header = document.createElement('div');
                header.className = 'text-black-500 px-3 py-1 text-xs uppercase tracking-wide';
                header.textContent = item.group;
                this.container.appendChild(header);
            }
            const row = document.createElement('div');
            row.setAttribute('role', 'option');
            row.setAttribute('aria-selected', String(index === this.selectedIndex));
            row.className = `text-black-800 cursor-pointer truncate px-3 py-1.5 text-sm ${index === this.selectedIndex ? 'bg-gray-100' : ''}`;
            row.textContent = item.label;
            // mousedown (not click) so the editor never loses focus/selection.
            row.addEventListener('mousedown', (event) => {
                event.preventDefault();
                this.command(item);
            });
            row.addEventListener('mouseenter', () => {
                this.selectedIndex = index;
                this.renderItems();
            });
            this.container.appendChild(row);
        });
    }

    onKeyDown(props: SuggestionKeyDownProps): boolean {
        if (!this.items.length) return false;
        if (props.event.key === 'ArrowDown') {
            this.selectedIndex = (this.selectedIndex + 1) % this.items.length;
            this.renderItems();
            return true;
        }
        if (props.event.key === 'ArrowUp') {
            this.selectedIndex = (this.selectedIndex - 1 + this.items.length) % this.items.length;
            this.renderItems();
            return true;
        }
        if (props.event.key === 'Enter' || props.event.key === 'Tab') {
            this.command(this.items[this.selectedIndex]);
            return true;
        }
        return false;
    }

    destroy() {
        this.container.remove();
    }
}

export interface AnswerPipeSuggestionOptions {
    /** Called on every keystroke after `@` — returns the (filtered) items. */
    getItems: (query: string) => PipeSuggestionItem[];
}

export const AnswerPipeSuggestion = Extension.create<AnswerPipeSuggestionOptions>({
    name: 'answerPipeSuggestion',

    addOptions() {
        return { getItems: () => [] };
    },

    addProseMirrorPlugins() {
        return [
            Suggestion<PipeSuggestionItem>({
                editor: this.editor,
                char: '@',
                allowSpaces: false,
                items: ({ query }) => this.options.getItems(query),
                command: ({ editor, range, props }) => {
                    editor
                        .chain()
                        .focus()
                        .insertContentAt(range, [{ type: 'answerPipe', attrs: { kind: props.kind, pipeKey: props.pipeKey, label: props.label } }, { type: 'text', text: ' ' }])
                        .run();
                },
                render: () => {
                    let list: PipeSuggestionList | null = null;
                    return {
                        onStart: (props) => {
                            list = new PipeSuggestionList();
                            list.update(props);
                        },
                        onUpdate: (props) => list?.update(props),
                        onKeyDown: (props) => {
                            if (props.event.key === 'Escape') {
                                list?.destroy();
                                list = null;
                                return true;
                            }
                            return list?.onKeyDown(props) ?? false;
                        },
                        onExit: () => {
                            list?.destroy();
                            list = null;
                        }
                    };
                }
            })
        ];
    }
});
