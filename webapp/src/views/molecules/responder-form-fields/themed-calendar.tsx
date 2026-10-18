'use client';

import * as React from 'react';

import { ChevronLeft, ChevronRight } from 'lucide-react';
import { DayPicker } from 'react-day-picker';

import { cn } from '@app/shadcn/util/lib';
import { useFormState } from '@app/store/jotai/form';
import { calendarColours } from '@app/utils/theme-contrast';

export type ThemedCalendarProps = React.ComponentProps<typeof DayPicker>;

/**
 * A Calendar component themed to match the form's FieldInput style: the
 * page colour as its ground, the button colour for the month and its days and
 * the chosen day, the border colour for weekday labels and today. Every text
 * colour is held to 4.5:1 on its ground (calendarColours), so a theme whose
 * own colours fall short gets a darker step of them.
 */
function ThemedCalendar({ className, classNames, showOutsideDays = true, ...props }: ThemedCalendarProps) {
    const { theme } = useFormState();
    const colours = calendarColours(theme);

    return (
        <DayPicker
            showOutsideDays={showOutsideDays}
            className={cn('p-3', className)}
            style={{ background: colours.background, ['--calendar-nav' as string]: colours.nav, ['--calendar-nav-hover' as string]: colours.day }}
            classNames={{
                months: 'flex flex-col sm:flex-row space-y-4 sm:space-x-4 sm:space-y-0',
                // `nav` is a sibling of month_caption (not its parent, as in v8), so
                // it's positioned absolute+inset-x-0 against this `relative` month
                // and spans the full width itself — justify-between then spreads
                // its two (normal-flow) button children to the left/right edges,
                // rather than each button being individually absolute-positioned
                // against nav's own (content-collapsed) box. month_caption comes
                // after nav in the DOM and covers the same strip, so nav is
                // stacked above it (z-10) or the caption swallows every click on
                // the month arrows; the bar itself lets clicks through, only its
                // buttons take them.
                month: 'relative space-y-4',
                month_caption: 'flex justify-center pt-1 items-center',
                caption_label: 'text-sm font-medium',
                nav: 'pointer-events-none absolute inset-x-0 top-1 z-10 flex items-center justify-between px-1',
                // The arrows are faded until hovered, as before, but never under
                // the 3:1 a control needs (WCAG 1.4.11).
                button_previous: 'pointer-events-auto h-7 w-7 bg-transparent p-0 text-(--calendar-nav) hover:text-(--calendar-nav-hover) disabled:cursor-not-allowed',
                button_next: 'pointer-events-auto h-7 w-7 bg-transparent p-0 text-(--calendar-nav) hover:text-(--calendar-nav-hover) disabled:cursor-not-allowed',
                month_grid: 'w-full border-collapse space-y-1',
                weekdays: 'flex',
                weekday: 'rounded-md w-9 font-normal text-[0.8rem]',
                week: 'flex w-full mt-2',
                // Modifier flags (selected/today/outside/...) and the aria-selected
                // attribute land on this cell in react-day-picker v10, not on
                // day_button, so the cell carries the colours (modifiersStyles
                // below) and the button inherits them.
                day: 'h-9 w-9 text-center text-sm p-0 relative focus-within:relative focus-within:z-20',
                day_button: 'h-9 w-9 rounded-[4px] p-0',
                selected: '',
                today: 'rounded-[4px]',
                // Told apart by a lighter weight and a softer (still 4.5:1) colour,
                // not by fading them below what can be read.
                outside: '',
                disabled: 'opacity-50',
                range_middle: '',
                hidden: 'invisible',
                ...classNames
            }}
            styles={{
                caption_label: { color: colours.day },
                weekday: { color: colours.weekday },
                day: { color: colours.day, fontWeight: 400 }
            }}
            // Applied in the order outside, today, selected: the chosen day wins.
            modifiersStyles={{
                outside: { color: colours.outside, fontWeight: 300 },
                today: { background: colours.todayBackground, color: colours.today },
                selected: { background: colours.selectedBackground, color: colours.selected, fontWeight: 400 }
            }}
            components={{
                Chevron: ({ orientation, ...props }) => (orientation === 'left' ? <ChevronLeft className="h-4 w-4" {...props} /> : <ChevronRight className="h-4 w-4" {...props} />)
            }}
            {...props}
        />
    );
}

ThemedCalendar.displayName = 'ThemedCalendar';

export { ThemedCalendar };
