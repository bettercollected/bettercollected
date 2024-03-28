import { cn } from '@app/shadcn/util/lib';
import Back from '@app/views/atoms/Icons/Back';

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
            <Back />
            <span className="text-sm font-normal">Back</span>
        </div>
    );
}
