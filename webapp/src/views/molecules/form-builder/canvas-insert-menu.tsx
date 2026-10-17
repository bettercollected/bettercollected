'use client';

import { useRef } from 'react';

import * as PopoverPrimitive from '@radix-ui/react-popover';
import { useSetAtom } from 'jotai';

import { StandardFormFieldDto } from '@app/models/dtos/form';
import { useActiveSlideComponent } from '@app/store/jotai/active-builder-component';
import useFormFieldsAtom from '@app/store/jotai/field-selectors';
import { InsertTarget, insertTargetAtom, useInsertTarget } from '@app/store/jotai/insert-target';
import InsertFieldComponent from '@app/views/molecules/dialogs/insert-field-modal';

/**
 * The Insert menu opened from the canvas ("/", Ctrl/Cmd+K or a "+" between
 * questions), placed next to where the field will go. One per page; it shows
 * while the insert target is on this page.
 */
export default function CanvasInsertMenu({ slide }: { slide: StandardFormFieldDto }) {
    const { insertTarget } = useInsertTarget();
    const open = !!insertTarget && insertTarget.slideId === slide?.id;
    if (!open) return null;
    return <OpenCanvasInsertMenu target={insertTarget} />;
}

/** The menu while it is open: only then does it follow the form. */
function OpenCanvasInsertMenu({ target: insertTarget }: { target: InsertTarget }) {
    const setInsertTarget = useSetAtom(insertTargetAtom);
    const { formFields } = useFormFieldsAtom();
    const { activeSlideComponent } = useActiveSlideComponent();
    const inserted = useRef(false);

    const anchorId = insertTarget.anchorId;
    const returnFocusId = insertTarget.returnFocusId;
    // Measured when Radix places the menu, so it follows the field.
    const virtualRef = {
        current: {
            getBoundingClientRect: () => document.getElementById(anchorId)?.getBoundingClientRect() ?? new DOMRect()
        }
    };

    return (
        <PopoverPrimitive.Root
            open
            onOpenChange={(next) => {
                if (!next) setInsertTarget(null);
            }}
        >
            <PopoverPrimitive.Anchor virtualRef={virtualRef} />
            <PopoverPrimitive.Portal>
                <PopoverPrimitive.Content
                    side="bottom"
                    align="start"
                    sideOffset={6}
                    collisionPadding={12}
                    aria-label="Insert a field"
                    className="z-popover overflow-hidden rounded border border-black-300 bg-white shadow-large outline-hidden"
                    onCloseAutoFocus={(event) => {
                        // Inserting focuses the new field; cancelling goes back
                        // to where "/" or the shortcut was pressed.
                        event.preventDefault();
                        if (!inserted.current && returnFocusId) document.getElementById(returnFocusId)?.focus();
                        inserted.current = false;
                    }}
                >
                    <InsertFieldComponent
                        formFields={formFields}
                        activeSlideComponent={activeSlideComponent}
                        target={insertTarget}
                        closeDropdown={() => {
                            inserted.current = true;
                            setInsertTarget(null);
                        }}
                    />
                </PopoverPrimitive.Content>
            </PopoverPrimitive.Portal>
        </PopoverPrimitive.Root>
    );
}
