import {
    Popover,
    PopoverContent,
    PopoverTrigger
} from '@app/shadcn/components/ui/popover';
import useFormFieldsAtom from '@app/store/jotai/fieldSelector';
import DeleteIcon from '@app/views/atoms/Icons/Delete';
import EllipsisOption from '@app/views/atoms/Icons/EllipsisOption';

export default function SlideOptions({ slideIndex }: { slideIndex: number }) {
    const { deleteSlide } = useFormFieldsAtom();
    return (
        <Popover>
            <PopoverTrigger>
                <EllipsisOption className="cursor-pointer" width={16} height={16} />
            </PopoverTrigger>
            <PopoverContent
                side="right"
                align="start"
                className="  w-[184px] bg-white p-0 shadow-lg"
            >
                <div
                    className=" p2 !my-2  flex cursor-pointer items-center gap-2 px-4 py-2 !text-red-500 hover:bg-red-50"
                    onClick={() => {
                        deleteSlide(slideIndex);
                    }}
                >
                    <DeleteIcon className="text-red-500" />
                    Delete
                </div>
            </PopoverContent>
        </Popover>
    );
}
