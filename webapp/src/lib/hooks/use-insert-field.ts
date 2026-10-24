'use client';

import { useEffect, useRef } from 'react';

import { v4 } from 'uuid';

import { InsertCatalogItem } from '@app/constants/insert-field-catalog';
import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import { FormSlideLayout } from '@app/models/enums/form';
import { useToast } from '@app/shadcn/components/ui/use-toast';
import { useActiveFieldComponent, useActiveSlideComponent } from '@app/store/jotai/active-builder-component';
import { useBuilderActions } from '@app/store/jotai/field-selectors';
import { InsertTarget } from '@app/store/jotai/insert-target';
import { useNavbarState } from '@app/store/jotai/navbar';

export type InsertPlacement = 'page' | 'new-page';

/** The canvas shows a new field this long after it is inserted. */
const FOCUS_DELAY_MS = 50;

/** Focus the new field's title on the canvas (or the field itself), so typing can start. */
function focusFieldTitle(fieldId: string) {
    const wrapper = document.getElementById(`scroll-field-${fieldId}`);
    wrapper?.scrollIntoView?.({ behavior: 'smooth', block: 'nearest' });
    const editor = wrapper?.querySelector<HTMLElement>('.ProseMirror[contenteditable="true"]');
    (editor ?? wrapper?.querySelector<HTMLElement>('[data-canvas-field]'))?.focus();
}

/**
 * Adds a field picked in the Insert menu.
 *
 * - `page` (the default): on the selected page, at the end; or, with a
 *   canvas `target`, at that position on that page.
 * - `new-page`: on a new page right after the selected one.
 *
 * Without any page yet, both make the first page.
 */
export function useInsertField() {
    const { toast } = useToast();
    const { activeSlideComponent, setActiveSlideComponent } = useActiveSlideComponent();
    const { setActiveFieldComponent } = useActiveFieldComponent();
    // The pages are read when a field is inserted, not subscribed to.
    const { getFormFields, addField, addFieldAt, addSlide, getNewField } = useBuilderActions();
    const { navbarState, setNavbarState } = useNavbarState();

    // What an insert schedules for a moment later (focusing the new field,
    // ending the slide-in) is cancelled when the builder unmounts: it must
    // not run on a canvas, or a document, that is gone.
    const pendingRef = useRef(new Set<() => void>());
    useEffect(() => {
        const pending = pendingRef.current;
        return () => {
            pending.forEach((cancel) => cancel());
            pending.clear();
        };
    }, []);
    const later = (run: () => void, ms: number) => {
        const cancel = () => window.clearTimeout(timer);
        const timer = window.setTimeout(() => {
            pendingRef.current.delete(cancel);
            run();
        }, ms);
        pendingRef.current.add(cancel);
    };

    const insert = (item: Pick<InsertCatalogItem, 'type' | 'name'>, placement: InsertPlacement = 'page', target?: InsertTarget | null): StandardFormFieldDto | null => {
        if (activeSlideComponent === null && !target) {
            toast({ description: 'Add a page to add fields' });
            return null;
        }
        const formFields = getFormFields();
        const fieldId = v4();
        const field = { ...getNewField({ ...item, icon: null }, fieldId, 0) } as StandardFormFieldDto;
        const selectedIndex = !activeSlideComponent || activeSlideComponent.index < 0 ? formFields.length - 1 : activeSlideComponent.index;

        if (target && placement === 'page' && formFields[target.slideIndex]) {
            addFieldAt(field, target.slideIndex, target.fieldIndex, target.replaceFieldId);
            const index = formFields[target.slideIndex]?.properties?.fields?.findIndex((f) => f.id === fieldId) ?? target.fieldIndex;
            setActiveSlideComponent({ id: formFields[target.slideIndex].id, index: target.slideIndex });
            setActiveFieldComponent({ id: fieldId, index });
        } else if (placement === 'page' && formFields[selectedIndex]) {
            const index = formFields[selectedIndex]?.properties?.fields?.length ?? 0;
            addField({ ...field, index }, selectedIndex);
            setActiveSlideComponent({ id: formFields[selectedIndex].id, index: selectedIndex });
            setActiveFieldComponent({ id: fieldId, index });
        } else {
            const slideId = v4();
            const newSlideIndex = !activeSlideComponent || activeSlideComponent.index < 0 ? formFields.length : activeSlideComponent.index + 1;
            addSlide(
                {
                    id: slideId,
                    index: newSlideIndex,
                    type: FieldTypes.SLIDE,
                    // New pages start calm: one column, no decorative image.
                    properties: { layout: FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND, fields: [{ ...field, index: 0 }] }
                },
                newSlideIndex
            );
            setActiveSlideComponent({ id: slideId, index: newSlideIndex });
            setActiveFieldComponent({ id: fieldId, index: 0 });
        }

        // The canvas slides the new field in (slide-builder reads insertClicked).
        setNavbarState({ ...navbarState, insertMenuOpen: false, insertClicked: true });
        later(() => setNavbarState((state: typeof navbarState) => ({ ...state, insertClicked: false })), 1000);
        later(() => focusFieldTitle(fieldId), FOCUS_DELAY_MS);
        return field;
    };

    return { insert };
}
