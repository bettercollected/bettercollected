import { cn } from '@app/shadcn/util/lib';
import BackChevron from '@app/views/atoms/Icons/BackChevron';

export default function BackButton({
    handleClick,
    className
}: {
    handleClick?: () => void;
    className?: string;
}) {
    const handleBackClick = async () => {
        handleClick && (await handleClick());
    };
    return (
        <div
            className={cn(
                'flex cursor-pointer items-center gap-1 py-4 text-black-900 hover:text-brand-500 hover:underline',
                className
            )}
            onClick={handleBackClick}
        >
            <BackChevron/>
            <span className=" font-normal">Back</span>
        </div>
    );
}
