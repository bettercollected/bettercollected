'use client';

import { useEffect, useRef } from 'react';

import { useUndoableDelete } from '@app/lib/hooks/use-undoable-delete';
import { useActiveFieldComponent, useActiveSlideComponent } from '@app/store/jotai/active-builder-component';
import { useBuilderActions } from '@app/store/jotai/field-selectors';
import { useInsertTarget } from '@app/store/jotai/insert-target';

/** Is focus somewhere typing goes: a text field, a select or a rich-text editor? */
export function isTypingTarget(target: EventTarget | null): boolean {
    const element = target as HTMLElement | null;
    if (!element || typeof element.closest !== 'function') return false;
    if (element.isContentEditable || element.closest('[contenteditable="true"]')) return true;
    const tag = element.tagName;
    if (tag === 'TEXTAREA' || tag === 'SELECT') return true;
    if (tag === 'INPUT') {
        const type = ((element as HTMLInputElement).type || 'text').toLowerCase();
        return !['checkbox', 'radio', 'button', 'submit', 'reset', 'range', 'color', 'file'].includes(type);
    }
    const role = element.getAttribute('role');
    return role === 'textbox' || role === 'combobox' || role === 'searchbox' || role === 'spinbutton';
}

/**
 * Focus is in a dialog, a menu or the page outline (whose rows and drag
 * handles use arrow keys, Space and Delete for their own keyboard moves):
 * their keys are their own.
 */
const OWN_KEYS = ['[role="dialog"]', '[role="alertdialog"]', '[role="menu"]', '[role="listbox"]', '[role="tree"]', '[data-outline-row]', '[data-outline-key]', '[aria-roledescription="sortable"]'].join(', ');
function isInOverlay(target: EventTarget | null): boolean {
    const element = target as HTMLElement | null;
    return !!element?.closest?.(OWN_KEYS);
}

/** Focus is on the page canvas (or nowhere in particular). */
function isOnCanvas(target: EventTarget | null): boolean {
    const element = target as HTMLElement | null;
    if (!element || element === document.body || element === document.documentElement) return true;
    return !!element.closest?.('[data-builder-canvas]');
}

export type BuilderShortcut = 'open-insert' | 'open-help' | 'move-up' | 'move-down' | 'duplicate' | 'delete' | 'previous-page' | 'next-page';

/**
 * Which builder shortcut a key press is, if any. Question shortcuts act on
 * the selected question and only while focus is on the canvas, never while
 * typing; Ctrl/Cmd+K opens the insert menu from anywhere.
 */
export function builderShortcutFor(event: Pick<KeyboardEvent, 'key' | 'ctrlKey' | 'metaKey' | 'altKey' | 'shiftKey' | 'target' | 'defaultPrevented'>, hasSelection: boolean): BuilderShortcut | null {
    if (event.defaultPrevented) return null;
    const mod = event.ctrlKey || event.metaKey;
    const key = event.key;
    if (mod && !event.altKey && !event.shiftKey && key.toLowerCase() === 'k') return isInOverlay(event.target) ? null : 'open-insert';
    if (isTypingTarget(event.target) || isInOverlay(event.target)) return null;
    if (mod && event.altKey && key === 'ArrowUp') return 'previous-page';
    if (mod && event.altKey && key === 'ArrowDown') return 'next-page';
    if (key === '?' && !mod && !event.altKey) return 'open-help';
    if (!isOnCanvas(event.target)) return null;
    if (key === '/' && !mod && !event.altKey && !event.shiftKey) return 'open-insert';
    if (!hasSelection) return null;
    if (event.altKey && !mod && key === 'ArrowUp') return 'move-up';
    if (event.altKey && !mod && key === 'ArrowDown') return 'move-down';
    if (mod && !event.altKey && !event.shiftKey && key.toLowerCase() === 'd') return 'duplicate';
    if ((key === 'Delete' || key === 'Backspace') && !mod && !event.altKey) return 'delete';
    return null;
}

/** Focus the canvas wrapper of the question at `index` on the page (after a move, copy or delete). */
function focusCanvasField(index: number) {
    window.setTimeout(() => {
        const fields = document.querySelectorAll<HTMLElement>('[data-builder-canvas] [data-canvas-field]');
        const target = fields[Math.min(index, fields.length - 1)];
        (target ?? document.querySelector<HTMLElement>('[data-builder-canvas]'))?.focus();
    }, 50);
}

/** Builder-wide keyboard authoring; mounted once (navbar). */
export function useBuilderShortcuts({ openHelp }: { openHelp: () => void }) {
    // The pages are read when a shortcut runs, not subscribed to.
    const { getFormFields, moveFieldInASlide, duplicateField } = useBuilderActions();
    const { deleteQuestion } = useUndoableDelete();
    const { activeFieldComponent, setActiveFieldComponent } = useActiveFieldComponent();
    const { activeSlideComponent, setActiveSlideComponent } = useActiveSlideComponent();
    const { setInsertTarget } = useInsertTarget();

    // One window listener; after each render it is handed the current
    // selection and the actions over the current builder state.
    const latest = useRef<{ hasSelection: boolean; run: (action: BuilderShortcut) => void }>({ hasSelection: false, run: () => {} });
    const run = (action: BuilderShortcut) => {
        const formFields = getFormFields();
        const slideIndex = activeSlideComponent?.index ?? -1;
        const slide = slideIndex >= 0 ? formFields?.[slideIndex] : undefined;
        const fields = slide?.properties?.fields ?? [];
        const fieldIndex = activeFieldComponent ? fields.findIndex((field) => field.id === activeFieldComponent.id) : -1;
        switch (action) {
            case 'open-help':
                openHelp();
                return;
            case 'open-insert': {
                if (!slide) return;
                const selected = fieldIndex >= 0 ? fields[fieldIndex] : undefined;
                setInsertTarget({
                    slideId: slide.id,
                    slideIndex,
                    fieldIndex: selected ? fieldIndex + 1 : fields.length,
                    anchorId: selected ? `scroll-field-${selected.id}` : `canvas-end-${slide.id}`,
                    returnFocusId: (document.activeElement as HTMLElement | null)?.id || undefined
                });
                return;
            }
            case 'move-up':
            case 'move-down': {
                if (fieldIndex < 0) return;
                const to = action === 'move-up' ? fieldIndex - 1 : fieldIndex + 1;
                if (to < 0 || to >= fields.length) return;
                moveFieldInASlide(slideIndex, fieldIndex, to);
                focusCanvasField(to);
                return;
            }
            case 'duplicate':
                if (fieldIndex < 0) return;
                duplicateField(slideIndex, fieldIndex);
                focusCanvasField(fieldIndex + 1);
                return;
            case 'delete':
                if (fieldIndex < 0) return;
                deleteQuestion(slideIndex, fieldIndex);
                focusCanvasField(fieldIndex);
                return;
            case 'previous-page':
            case 'next-page': {
                // Welcome page, the question pages, then the ending page.
                const order = [{ id: 'welcome-page', index: -10 }, ...(formFields ?? []).map((page, index) => ({ id: page.id, index })), { id: 'thank-you-page', index: -20 }];
                const at = Math.max(
                    0,
                    order.findIndex((page) => page.index === (activeSlideComponent?.index ?? -10))
                );
                const next = order[action === 'previous-page' ? at - 1 : at + 1];
                if (!next) return;
                setActiveFieldComponent(null);
                setActiveSlideComponent(next);
                return;
            }
        }
    };

    useEffect(() => {
        latest.current = { hasSelection: !!activeFieldComponent, run };
    });

    useEffect(() => {
        const onKeyDown = (event: KeyboardEvent) => {
            const action = builderShortcutFor(event, latest.current.hasSelection);
            if (!action) return;
            event.preventDefault();
            latest.current.run(action);
        };
        window.addEventListener('keydown', onKeyDown);
        return () => window.removeEventListener('keydown', onKeyDown);
    }, []);
}

/** The shortcuts the help popover lists. */
export const BUILDER_SHORTCUTS: Array<{ keys: string[]; label: string }> = [
    { keys: ['/'], label: 'Insert a field (on the canvas, or in an empty question or text block)' },
    { keys: ['Ctrl/⌘', 'K'], label: 'Insert a field after the selected question' },
    { keys: ['Alt', '↑'], label: 'Move the selected question up' },
    { keys: ['Alt', '↓'], label: 'Move the selected question down' },
    { keys: ['Ctrl/⌘', 'D'], label: 'Duplicate the selected question' },
    { keys: ['Delete'], label: 'Delete the selected question (Undo in the message)' },
    { keys: ['Ctrl/⌘', 'Alt', '↑'], label: 'Previous page' },
    { keys: ['Ctrl/⌘', 'Alt', '↓'], label: 'Next page' },
    { keys: ['Ctrl/⌘', 'Z'], label: 'Undo' },
    { keys: ['Ctrl/⌘', 'Shift', 'Z'], label: 'Redo' },
    { keys: ['?'], label: 'Show these shortcuts' }
];
