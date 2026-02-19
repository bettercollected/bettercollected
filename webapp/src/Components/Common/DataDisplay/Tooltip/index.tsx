import React from 'react';
import { Tooltip as ShadcnTooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@app/shadcn/components/ui/tooltip';

interface ITooltipProps {
    title: React.ReactNode;
    children: React.ReactElement<any>;
    className?: string;
    placement?: 'bottom' | 'bottom-end' | 'bottom-start' | 'left-end' | 'left-start' | 'left' | 'right-end' | 'right-start' | 'right' | 'top-end' | 'top-start' | 'top';
    // Keeping other props optional to avoid breaking types, but might not implement all
    [key: string]: any;
}

export default function Tooltip({
    title,
    children,
    className = '',
    placement = 'bottom',
    enterDelay = 100,
    disableHoverListener = false,
    ...props
}: ITooltipProps) {
    if (!title || disableHoverListener) return <>{children}</>;

    const getSideAndAlign = (placement: string) => {
        const [side, align] = placement.split('-');
        return {
            side: side as "top" | "right" | "bottom" | "left",
            align: (align as "start" | "center" | "end") || "center"
        };
    };

    const { side, align } = getSideAndAlign(placement);

    return (
        <TooltipProvider delayDuration={enterDelay}>
            <ShadcnTooltip>
                <TooltipTrigger asChild>
                    <span className={className}>{children}</span>
                </TooltipTrigger>
                <TooltipContent side={side} align={align} className="z-[50]">
                    {title}
                </TooltipContent>
            </ShadcnTooltip>
        </TooltipProvider>
    );
}
