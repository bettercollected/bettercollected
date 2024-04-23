import { cn } from '@app/shadcn/util/lib';
import BackChevron from '@app/views/atoms/Icons/BackChevron';

export default function BackButton({ handleClick, className }: { handleClick?: () => void; className?: string }) {
    const handleBackClick = async () => {
        handleClick && (await handleClick());
    };
    return (
        <div className={cn('text-black-600 hover:text-brand-500 flex cursor-pointer items-center gap-[2px] py-4 hover:underline', className)} onClick={handleBackClick}>
            <BackChevron />
            <span className=" font-normal">Back</span>
        </div>
    );
}
