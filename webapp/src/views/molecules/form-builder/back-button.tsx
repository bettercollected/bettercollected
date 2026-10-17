import { cn } from '@app/shadcn/util/lib';
import BackChevron from '@Components/icons/back-chevron';
import { CSSProperties } from 'react';

export default function BackButton({
    handleClick,
    className,
    hideForSmallScreen = false,
    style,
    label = 'Back'
}: {
    handleClick?: () => void;
    className?: string;
    hideForSmallScreen?: boolean;
    style?: CSSProperties;
    /** Visible text and accessible name (respondent forms pass it in the respondent's language). */
    label?: string;
}) {
    const handleBackClick = async () => {
        handleClick && (await handleClick());
    };
    return (
        <button type="button" aria-label={label} className={cn('hover:bg-black-200! text-black-600 hover:text-black-800! flex cursor-pointer items-center gap-[2px] rounded-[4px] p-1 py-[6px]', className)} onClick={handleBackClick} style={style}>
            <BackChevron className="h-5 w-5" />
            <span className={`p3-new font-normal ${hideForSmallScreen ? 'hidden lg:flex' : ''}`}>{label}</span>
        </button>
    );
}
