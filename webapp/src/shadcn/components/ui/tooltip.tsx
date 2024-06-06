'use client';

import * as React from 'react';

import * as TooltipPrimitive from '@radix-ui/react-tooltip';

import { cn } from '@app/shadcn/util/lib';

interface ICustomTooltip {
    children: React.ReactNode;
    label: string;
    className?: string;
    triggerClassName?: string;
}

const TooltipProvider = TooltipPrimitive.Provider;

const Tooltip = TooltipPrimitive.Root;

const TooltipTrigger = TooltipPrimitive.Trigger;

const TooltipContent = React.forwardRef<React.ElementRef<typeof TooltipPrimitive.Content>, React.ComponentPropsWithoutRef<typeof TooltipPrimitive.Content>>(({ className, sideOffset = 4, ...props }, ref) => (
    <TooltipPrimitive.Content ref={ref} sideOffset={sideOffset} className={cn('bg-black-800 z-50 overflow-hidden rounded-md border px-3 py-1.5 text-sm text-white shadow-md', className)} {...props} />
));
TooltipContent.displayName = TooltipPrimitive.Content.displayName;

export default function ToolTip({ children, label, className, triggerClassName }: ICustomTooltip) {
    return (
        <TooltipProvider>
            <Tooltip delayDuration={300}>
                <TooltipTrigger className={triggerClassName}>{children}</TooltipTrigger>
                <TooltipContent className={className}>{label}</TooltipContent>
            </Tooltip>
        </TooltipProvider>
    );
}

// export { Tooltip, TooltipTrigger, TooltipContent, TooltipProvider }
