'use client';

import { useRef } from 'react';

import * as DropdownMenuPrimitive from '@radix-ui/react-dropdown-menu';
import { Copy, Ellipsis, PencilLine, Star, Trash2 } from 'lucide-react';

import { DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator } from '@app/shadcn/components/ui/dropdown-menu';
import { cn } from '@app/shadcn/util/lib';

import { outlineMenuItemClass, outlineMenuTriggerClass } from '../slide-options';

/**
 * An ending's "…" menu in the outline: rename, duplicate, make it the
 * default, delete (never the last one; the toast offers Undo).
 */
export default function EndingOptions({
    label,
    visible,
    isDefault,
    canDelete,
    onRename,
    onDuplicate,
    onMakeDefault,
    onDelete
}: {
    label: string;
    visible: boolean;
    isDefault: boolean;
    canDelete: boolean;
    onRename: () => void;
    onDuplicate: () => void;
    onMakeDefault: () => void;
    onDelete: () => void;
}) {
    // Rename hands focus to the name field instead of back to this trigger.
    const renaming = useRef(false);
    return (
        <DropdownMenuPrimitive.Root>
            <DropdownMenuPrimitive.Trigger aria-label={`Options for ${label}`} className={outlineMenuTriggerClass(visible)}>
                <Ellipsis className="h-4 w-4" aria-hidden="true" />
            </DropdownMenuPrimitive.Trigger>
            <DropdownMenuContent
                side="right"
                align="start"
                className="w-[200px] bg-white"
                onCloseAutoFocus={(event) => {
                    if (renaming.current) event.preventDefault();
                    renaming.current = false;
                }}
            >
                <DropdownMenuItem
                    className={outlineMenuItemClass}
                    onSelect={() => {
                        renaming.current = true;
                        onRename();
                    }}
                >
                    <PencilLine className="h-4 w-4" aria-hidden="true" />
                    Rename
                </DropdownMenuItem>
                <DropdownMenuItem className={outlineMenuItemClass} onSelect={onDuplicate}>
                    <Copy className="h-4 w-4" aria-hidden="true" />
                    Duplicate
                </DropdownMenuItem>
                <DropdownMenuItem className={outlineMenuItemClass} disabled={isDefault} onSelect={onMakeDefault}>
                    <Star className="h-4 w-4" aria-hidden="true" />
                    Make default
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem className={cn(outlineMenuItemClass, 'text-[#C43D3D] focus:bg-[#FBEFEF] focus:text-[#C43D3D]')} disabled={!canDelete} onSelect={onDelete}>
                    <Trash2 className="h-4 w-4" aria-hidden="true" />
                    {canDelete ? 'Delete' : 'Delete (a form keeps one ending)'}
                </DropdownMenuItem>
            </DropdownMenuContent>
        </DropdownMenuPrimitive.Root>
    );
}
