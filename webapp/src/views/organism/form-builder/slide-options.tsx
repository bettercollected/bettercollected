import { useState } from 'react';

import { Popover, PopoverContent, PopoverTrigger } from '@app/shadcn/components/ui/popover';
import { cn } from '@app/shadcn/util/lib';
import { useActiveSlideComponent } from '@app/store/jotai/active-builder-component';
import useFormFieldsAtom from '@app/store/jotai/field-selectors';
import DeleteIcon from '@Components/icons/delete';
import EllipsisOption from '@Components/icons/ellipsis-option';
import { Copy } from 'lucide-react';

export default function SlideOptions({ slideIndex }: { slideIndex: number }) {
    const { formFields, deleteSlide, duplicateSlide } = useFormFieldsAtom();
    const { activeSlideComponent } = useActiveSlideComponent();
    const [open, setOpen] = useState(false);
    const [confirmingDelete, setConfirmingDelete] = useState(false);

    const questionCount = formFields?.[slideIndex]?.properties?.fields?.length ?? 0;

    const close = () => {
        setOpen(false);
        setConfirmingDelete(false);
    };

    return (
        <Popover
            open={open}
            onOpenChange={(next) => {
                setOpen(next);
                if (!next) setConfirmingDelete(false);
            }}
        >
            <PopoverTrigger>
                <EllipsisOption className={cn(' hidden cursor-pointer', activeSlideComponent?.index === slideIndex && 'block', 'group-hover:block')} width={16} height={16} />
            </PopoverTrigger>
            <PopoverContent side="right" align="start" className=" w-[220px]  bg-white p-0 shadow-lg">
                <div
                    className="p2 !mt-2 flex cursor-pointer items-center gap-2 px-4 py-2 hover:bg-gray-100"
                    onClick={() => {
                        duplicateSlide(slideIndex);
                        close();
                    }}
                >
                    <Copy className="h-4 w-4" />
                    Duplicate
                </div>
                {!confirmingDelete ? (
                    <div className=" p2 !mb-2  flex cursor-pointer items-center gap-2 px-4 py-2 !text-red-500 hover:bg-red-50" onClick={() => setConfirmingDelete(true)}>
                        <DeleteIcon className="text-red-500" />
                        Delete
                    </div>
                ) : (
                    // Deleting a page silently rewrites any logic that pointed at
                    // it — say what happens before doing it.
                    <div className="mb-2 flex flex-col gap-2 px-4 py-2">
                        <span className="text-black-800 text-sm font-medium">Delete this page?</span>
                        <span className="text-black-600 text-xs leading-relaxed">
                            {questionCount > 0 ? `Removes ${questionCount} question${questionCount === 1 ? '' : 's'}; logic pointing here is cleaned up.` : 'Logic pointing here is cleaned up.'} Undo restores it.
                        </span>
                        <div className="flex gap-2">
                            <button
                                className="rounded-md bg-[#C43D3D] px-3 py-1 text-xs font-semibold text-white hover:bg-[#a83434]"
                                onClick={() => {
                                    deleteSlide(slideIndex);
                                    close();
                                }}
                            >
                                Delete page
                            </button>
                            <button className="text-black-700 hover:bg-black-100 rounded-md border px-3 py-1 text-xs font-medium" onClick={() => setConfirmingDelete(false)}>
                                Cancel
                            </button>
                        </div>
                    </div>
                )}
            </PopoverContent>
        </Popover>
    );
}
