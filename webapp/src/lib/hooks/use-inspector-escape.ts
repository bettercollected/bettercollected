'use client';

import { useEffect } from 'react';

import { useActiveFieldComponent } from '@app/store/jotai/active-builder-component';
import { PropertiesTab, usePropertiesTab } from '@app/store/jotai/properties-tab';

/** Where the builder's inspector (the right sidebar) is: the form, a page or a question. */
export type InspectorLevel = 'form' | 'page' | 'question';

export function inspectorLevel(hasActiveField: boolean, tab: PropertiesTab): InspectorLevel {
    if (hasActiveField) return 'question';
    return tab === 'page' ? 'page' : 'form';
}

// Surfaces that own their Escape: when focus is in one, or one is open,
// Escape closes that, not the inspector level.
const ESCAPE_OWNERS = '[role="dialog"], [role="alertdialog"], [role="menu"], [role="listbox"], [aria-modal="true"], [data-radix-popper-content-wrapper]';
const OPEN_OVERLAYS = '[role="dialog"][data-state="open"], [role="alertdialog"][data-state="open"], [aria-modal="true"]';

const isEditable = (element: Element | null) => !!element && (element.matches('input, textarea, select') || (element as HTMLElement).isContentEditable);

/**
 * Whether the inspector should leave this keydown alone: not Escape, or
 * Escape that something else already handled (a popover, a menu, a dialog,
 * an editor's suggestion list: Radix and ProseMirror mark it handled with
 * preventDefault) or that belongs to an open dialog.
 */
export function escapeBelongsElsewhere(event: KeyboardEvent): boolean {
    if (event.key !== 'Escape' || event.defaultPrevented || event.isComposing) return true;
    const target = event.target instanceof Element ? event.target : null;
    if (target?.closest(ESCAPE_OWNERS)) return true;
    return !!document.querySelector(OPEN_OVERLAYS);
}

/** Bring keyboard focus to the inspector's current breadcrumb, if focus was lost with the panel it was in. */
function refocusInspector(hadFocusInInspector: boolean) {
    if (!hadFocusInInspector) return;
    requestAnimationFrame(() => {
        if (document.activeElement && document.activeElement !== document.body && document.contains(document.activeElement)) return;
        document.querySelector<HTMLElement>('[data-inspector-current]')?.focus();
    });
}

/**
 * Escape goes up one inspector level: question → page → form. From the
 * page level only when not typing (Escape in a text box is not a request to
 * leave the page's settings). Mount once per builder.
 */
export function useInspectorEscape() {
    const { activeFieldComponent, setActiveFieldComponent } = useActiveFieldComponent();
    const { propertiesTab, setPropertiesTab } = usePropertiesTab();
    const level = inspectorLevel(!!activeFieldComponent?.id, propertiesTab);

    useEffect(() => {
        const onKeyDown = (event: KeyboardEvent) => {
            if (escapeBelongsElsewhere(event)) return;
            const hadFocusInInspector = !!document.activeElement?.closest('[data-inspector]');
            if (level === 'question') {
                setActiveFieldComponent(null);
                setPropertiesTab('page');
                refocusInspector(hadFocusInInspector);
            } else if (level === 'page' && !isEditable(event.target instanceof Element ? event.target : null)) {
                setPropertiesTab('form');
                refocusInspector(hadFocusInInspector);
            }
        };
        window.addEventListener('keydown', onKeyDown);
        return () => window.removeEventListener('keydown', onKeyDown);
    }, [level, setActiveFieldComponent, setPropertiesTab]);
}
