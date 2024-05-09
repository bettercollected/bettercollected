import { cn } from '@app/shadcn/util/lib';
import BackChevron from '@app/views/atoms/Icons/BackChevron';

export default function BackButton({ handleClick, className, hideForSmallScreen = false }: { handleClick?: () => void; className?: string; hideForSmallScreen?: boolean }) {
    const handleBackClick = async () => {
        handleClick && (await handleClick());
    };
    return (
        <div className={cn('hover:bg-black-200 text-black-600 hover:text-black-800 flex cursor-pointer items-center gap-[2px] rounded-lg p-1 py-[6px]', className)} onClick={handleBackClick}>
            <BackChevron className="h-5 w-5" />
            <span className={`p3-new font-normal ${hideForSmallScreen ? 'hidden lg:flex' : ''}`}>Back</span>
        </div>
    );
}
