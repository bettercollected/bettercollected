import { useState } from 'react';

import { MoreHorizontal } from 'lucide-react';
import { useTranslation } from 'next-i18next';

import Delete from '@app/components/Common/Icons/Common/Delete';
import { Popover, PopoverContent, PopoverTrigger } from '@app/shadcn/components/ui/popover';

import { localesCommon } from '@app/constants/locales/common';


export default function DeleteDropDown({ onDropDownItemClick, className, label }: { onDropDownItemClick: (event?: any) => void; className?: string; label?: string }) {
    const { t } = useTranslation();

    const [open, setOpen] = useState(false);
    return (
        <Popover open={open} onOpenChange={setOpen}>
            <PopoverTrigger asChild>
                <div
                    className={`${className} cursor-pointer`}
                    onClick={(e) => {
                        e.stopPropagation();
                        e.preventDefault();
                    }}
                >
                    <MoreHorizontal className="text-black-600 w-5 h-5" />
                </div>
            </PopoverTrigger>
            <PopoverContent
                className="w-[200px] p-0 rounded-lg drop-shadow-xl"
                align="end"
                onClick={() => setOpen(false)}
            >
                <div
                    className="flex items-center gap-4 px-4 py-3 hover:bg-black-100 cursor-pointer text-sm"
                    onClick={(event) => {
                        event.stopPropagation();
                        onDropDownItemClick(event);
                    }}
                >
                    <Delete width={20} height={20} />
                    {label ?? t(localesCommon.remove)}
                </div>
            </PopoverContent>
        </Popover>
    );
}