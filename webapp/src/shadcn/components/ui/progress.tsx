'use client';

import * as React from 'react';

import * as ProgressPrimitive from '@radix-ui/react-progress';

import { cn } from '@app/shadcn/util/lib';

const Progress = React.forwardRef<React.ElementRef<typeof ProgressPrimitive.Root>, React.ComponentPropsWithoutRef<typeof ProgressPrimitive.Root> & { indicatorColor?: string }>(({ className, value, indicatorColor, ...props }, ref) => (
    <ProgressPrimitive.Root ref={ref} value={value} className={cn('relative h-2 w-full overflow-hidden rounded-full bg-white', className)} {...props}>
        <ProgressPrimitive.Indicator className="h-full w-full flex-1 transition-transform duration-300 ease-out motion-reduce:transition-none" style={{ transform: `translateX(-${100 - (value || 0)}%)`, background: indicatorColor }} />
    </ProgressPrimitive.Root>
));
Progress.displayName = ProgressPrimitive.Root.displayName;

export { Progress };
