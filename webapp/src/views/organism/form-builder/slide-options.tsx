import { useState } from 'react';

import { useUndoableDelete } from '@app/lib/hooks/use-undoable-delete';
import { Popover, PopoverContent, PopoverTrigger } from '@app/shadcn/components/ui/popover';
import { cn } from '@app/shadcn/util/lib';
import { useActiveSlideComponent } from '@app/store/jotai/active-builder-component';
import useFormFieldsAtom from '@app/store/jotai/field-selectors';
import DeleteIcon from '@Components/icons/delete';
import EllipsisOption from '@Components/icons/ellipsis-option';
import { Copy } from 'lucide-react';

export default function SlideOptions({ slideIndex }: { slideIndex: number }) {
    const { duplicateSlide } = useFormFieldsAtom();
    const { deletePage } = useUndoableDelete();
    const { activeSlideComponent } = useActiveSlideComponent();
    const [open, setOpen] = useState(false);

    return (
        <Popover open={open} onOpenChange={setOpen}>
            <PopoverTrigger>
                <EllipsisOption className={cn(' hidden cursor-pointer', activeSlideComponent?.index === slideIndex && 'block', 'group-hover:block')} width={16} height={16} />
            </PopoverTrigger>
            <PopoverContent side="right" align="start" className=" w-[220px]  bg-white p-0 shadow-large">
                <div
                    className="p2 mt-2! flex cursor-pointer items-center gap-2 px-4 py-2 hover:bg-gray-100"
                    onClick={() => {
                        duplicateSlide(slideIndex);
                        setOpen(false);
                    }}
                >
                    <Copy className="h-4 w-4" />
                    Duplicate
                </div>
                {/* Deletes at once; the toast (and the toolbar's Undo) brings
                    the page back, with its questions and the logic that
                    pointed at them. */}
                <div
                    className=" p2 mb-2!  flex cursor-pointer items-center gap-2 px-4 py-2 text-red-500! hover:bg-red-50"
                    onClick={() => {
                        setOpen(false);
                        deletePage(slideIndex);
                    }}
                >
                    <DeleteIcon className="text-red-500" />
                    Delete
                </div>
            </PopoverContent>
        </Popover>
    );
}
