import { useRef } from 'react';

import * as DropdownMenuPrimitive from '@radix-ui/react-dropdown-menu';
import { ArrowDown, ArrowUp, Copy, Ellipsis, Trash2 } from 'lucide-react';

import { useUndoableDelete } from '@app/lib/hooks/use-undoable-delete';
import { DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator } from '@app/shadcn/components/ui/dropdown-menu';
import { cn } from '@app/shadcn/util/lib';
import useFormFieldsAtom from '@app/store/jotai/field-selectors';

import { MoveOutcome, useOutlineMoves } from './outline/use-outline-moves';

/** The outline's "…" trigger: shown on row hover, on focus, while open and on the selected row. */
export const outlineMenuTriggerClass = (visible: boolean) =>
    cn(
        'text-black-600 hover:bg-black-300 hover:text-black-900 flex h-6 w-6 shrink-0 items-center justify-center rounded-sm transition-opacity',
        'focus-visible:opacity-100 group-hover/row:opacity-100 data-[state=open]:opacity-100 pointer-coarse:opacity-100',
        visible ? 'opacity-100' : 'opacity-0'
    );

export const outlineMenuItemClass = 'text-black-800 gap-2 px-3 py-2 text-sm';

/**
 * A page's "…" menu in the outline: move it, duplicate it, delete it (the
 * delete toast offers Undo, with its questions and the logic that used them).
 */
export default function SlideOptions({ slideIndex, pageName, visible, onMoved }: { slideIndex: number; pageName: string; visible: boolean; onMoved: (outcome: MoveOutcome) => void }) {
    const { formFields, duplicateSlide } = useFormFieldsAtom();
    const { deletePage } = useUndoableDelete();
    const { movePageTo } = useOutlineMoves();
    // A move hands focus to the moved row instead of back to this trigger.
    const moved = useRef(false);
    const move = (to: number) => {
        moved.current = true;
        onMoved(movePageTo(slideIndex, to));
    };

    return (
        <DropdownMenuPrimitive.Root>
            <DropdownMenuPrimitive.Trigger aria-label={`Options for ${pageName}`} className={outlineMenuTriggerClass(visible)}>
                <Ellipsis className="h-4 w-4" aria-hidden="true" />
            </DropdownMenuPrimitive.Trigger>
            <DropdownMenuContent
                side="right"
                align="start"
                className="w-[200px] bg-white"
                onCloseAutoFocus={(event) => {
                    if (moved.current) event.preventDefault();
                    moved.current = false;
                }}
            >
                <DropdownMenuItem className={outlineMenuItemClass} disabled={slideIndex === 0} onSelect={() => move(slideIndex - 1)}>
                    <ArrowUp className="h-4 w-4" aria-hidden="true" />
                    Move up
                </DropdownMenuItem>
                <DropdownMenuItem className={outlineMenuItemClass} disabled={slideIndex >= formFields.length - 1} onSelect={() => move(slideIndex + 1)}>
                    <ArrowDown className="h-4 w-4" aria-hidden="true" />
                    Move down
                </DropdownMenuItem>
                <DropdownMenuItem className={outlineMenuItemClass} onSelect={() => duplicateSlide(slideIndex)}>
                    <Copy className="h-4 w-4" aria-hidden="true" />
                    Duplicate
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                {/* Deletes at once; the toast (and the toolbar's Undo) brings
                    the page back, with its questions and the logic that
                    pointed at them. */}
                <DropdownMenuItem className={cn(outlineMenuItemClass, 'text-[#C43D3D] focus:bg-[#FBEFEF] focus:text-[#C43D3D]')} onSelect={() => deletePage(slideIndex)}>
                    <Trash2 className="h-4 w-4" aria-hidden="true" />
                    Delete
                </DropdownMenuItem>
            </DropdownMenuContent>
        </DropdownMenuPrimitive.Root>
    );
}
