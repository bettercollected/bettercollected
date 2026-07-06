'use client';

import * as React from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { DayPicker } from 'react-day-picker';

import { cn } from '@app/shadcn/util/lib';
import { buttonVariants } from '@app/shadcn/components/ui/button';

export type CalendarProps = React.ComponentProps<typeof DayPicker>;

function Calendar({ className, classNames, showOutsideDays = true, ...props }: CalendarProps) {
    return (
        <DayPicker
            showOutsideDays={showOutsideDays}
            className={cn('p-3', className)}
            classNames={{
                months: 'flex flex-col sm:flex-row space-y-4 sm:space-x-4 sm:space-y-0',
                // `nav` is a sibling of month_caption (not its parent, as in v8), so
                // it's positioned absolute+inset-x-0 against this `relative` month
                // and spans the full width itself — justify-between then spreads
                // its two (normal-flow) button children to the left/right edges,
                // rather than each button being individually absolute-positioned
                // against nav's own (content-collapsed) box.
                month: 'relative space-y-4',
                month_caption: 'flex justify-center pt-1 items-center',
                caption_label: 'text-sm font-medium',
                nav: 'absolute inset-x-0 top-1 flex items-center justify-between px-1',
                button_previous: cn('h-7 w-7 bg-transparent p-0 opacity-50 hover:opacity-100', 'hover:!opacity-50 disabled:cursor-not-allowed'),
                button_next: cn('h-7 w-7 bg-transparent p-0 opacity-50 hover:opacity-100'),
                month_grid: 'w-full border-collapse space-y-1 ',
                weekdays: 'flex',
                weekday: 'text-muted-foreground rounded-md w-9 font-normal text-[0.8rem]',
                week: 'flex w-full mt-2',
                // The grid cell — modifier flags (selected/today/outside/...) and
                // aria-selected/data-* attributes now land here (react-day-picker
                // v10), not on day_button, so the state-driven classes below target
                // this key instead of the old `cell`/`day` split.
                day: 'h-9 w-9 text-center text-sm p-0 relative focus-within:relative focus-within:z-20',
                day_button: cn('h-9 w-9 rounded p-0 font-normal bg-transparent hover:bg-gray-100'),
                range_end: 'rounded-r-md',
                selected:
                    'bg-primary text-primary-foreground bg-black text-white hover:!bg-black hover:!text-white focus-within:bg-primary focus-within:text-primary-foreground first:rounded-l-md last:rounded-r-md',
                today: 'bg-accent text-accent-foreground bg-gray-100 rounded aria-selected:bg-black aria-selected:text-white',
                outside: 'text-muted-foreground opacity-50 aria-selected:bg-accent/50 aria-selected:text-muted-foreground aria-selected:opacity-30',
                disabled: 'text-muted-foreground opacity-50',
                range_middle: 'aria-selected:bg-accent aria-selected:text-accent-foreground',
                hidden: 'invisible',
                ...classNames
            }}
            components={{
                Chevron: ({ orientation, ...props }) =>
                    orientation === 'left' ? <ChevronLeft className="h-4 w-4" {...props} /> : <ChevronRight className="h-4 w-4" {...props} />
            }}
            {...props}
        />
    );
}
Calendar.displayName = 'Calendar';

export { Calendar };
