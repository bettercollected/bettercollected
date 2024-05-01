'use client';

import * as React from 'react';

import * as ScrollAreaPrimitive from '@radix-ui/react-scroll-area';

import { cn } from '@app/shadcn/util/lib';

type ExtendedScrollbarProps = React.ComponentPropsWithoutRef<typeof ScrollAreaPrimitive.ScrollAreaScrollbar> & {
    thumbBg?: string; // or whatever type thumbBg should be
};

const ScrollArea = React.forwardRef<React.ElementRef<typeof ScrollAreaPrimitive.Root>, React.ComponentPropsWithoutRef<typeof ScrollAreaPrimitive.Root> & ExtendedScrollbarProps>(({ className, children, asChild, id, ...props }, ref) => (
    <ScrollAreaPrimitive.Root ref={ref} className={cn('relative overflow-hidden', className)} {...props}>
        <ScrollAreaPrimitive.Viewport style={{ display: 'block !important' }} asChild={asChild} id={id} className="!block h-full w-full rounded-[inherit]">
            {children}
        </ScrollAreaPrimitive.Viewport>
        <ScrollBar thumbBg={props.thumbBg} />
        <ScrollAreaPrimitive.Corner />
    </ScrollAreaPrimitive.Root>
));
ScrollArea.displayName = ScrollAreaPrimitive.Root.displayName;

const ScrollBar = React.forwardRef<React.ElementRef<typeof ScrollAreaPrimitive.ScrollAreaScrollbar>, ExtendedScrollbarProps>(({ className, orientation = 'vertical', thumbBg, ...props }, ref) => (
    <ScrollAreaPrimitive.ScrollAreaScrollbar
        ref={ref}
        orientation={orientation}
        className={cn('flex touch-none select-none transition-colors', orientation === 'vertical' && 'h-full w-2.5 border-l border-l-transparent p-[1px]', orientation === 'horizontal' && 'h-2.5 flex-col border-t border-t-transparent p-[1px]', className)}
        {...props}
    >
        <ScrollAreaPrimitive.ScrollAreaThumb className="bg-black-200 relative flex-1 rounded-full" style={{ background: thumbBg }} />
    </ScrollAreaPrimitive.ScrollAreaScrollbar>
));
ScrollBar.displayName = ScrollAreaPrimitive.ScrollAreaScrollbar.displayName;

export { ScrollArea, ScrollBar };
