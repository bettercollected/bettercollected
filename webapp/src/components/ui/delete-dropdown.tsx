import { useState } from 'react';

import { MoreHorizontal, Trash2 } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@app/shadcn/components/ui/dropdown-menu';
import { cn } from '@app/shadcn/util/lib';

import { localesCommon } from '@app/constants/locales/common';

interface DeleteDropDownProps {
    onDropDownItemClick: (event?: any) => void;
    className?: string;
    /** The menu item's text; "Remove" when not given. */
    label?: string;
    /** What the menu acts on (a form title, an email, ...): the trigger is named "More actions for <itemName>". */
    itemName?: string;
}

/**
 * A "more" (three dots) button that opens a menu with one remove/delete item.
 * The trigger is a real button, so it is reachable and opens with the
 * keyboard; the menu is the app's Radix dropdown menu (arrow keys, Escape
 * closes and returns focus to the button).
 */
export default function DeleteDropDown({ onDropDownItemClick, className, label, itemName }: DeleteDropDownProps) {
    const { t } = useTranslation();

    const [open, setOpen] = useState(false);
    return (
        <DropdownMenu open={open} onOpenChange={setOpen}>
            <DropdownMenuTrigger asChild>
                <button
                    type="button"
                    aria-label={itemName ? t(localesCommon.moreActionsFor, { name: itemName }) : t(localesCommon.moreActions)}
                    className={cn('text-black-600 hover:bg-black-100 inline-flex cursor-pointer items-center justify-center rounded p-1', className)}
                    // Call sites sit inside clickable cards and table rows: opening
                    // the menu must not also open the card or row.
                    onClick={(e) => {
                        e.stopPropagation();
                        e.preventDefault();
                    }}
                >
                    <MoreHorizontal className="h-5 w-5" aria-hidden="true" />
                </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent className="w-[200px] rounded bg-white p-0" align="end">
                <DropdownMenuItem
                    className="hover:bg-black-100 flex cursor-pointer items-center gap-4 px-4 py-3 text-sm"
                    onClick={(event) => {
                        // Close explicitly: call sites call preventDefault, which
                        // would otherwise keep the menu open.
                        event.stopPropagation();
                        setOpen(false);
                        onDropDownItemClick(event);
                    }}
                >
                    <Trash2 width={20} height={20} aria-hidden="true" />
                    {label ?? t(localesCommon.remove)}
                </DropdownMenuItem>
            </DropdownMenuContent>
        </DropdownMenu>
    );
}
