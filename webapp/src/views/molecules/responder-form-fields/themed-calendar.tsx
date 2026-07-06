'use client';

import * as React from 'react';

import { ChevronLeft, ChevronRight } from 'lucide-react';
import { DayPicker } from 'react-day-picker';

import { cn } from '@app/shadcn/util/lib';
import { useFormState } from '@app/store/jotai/form';

export type ThemedCalendarProps = React.ComponentProps<typeof DayPicker>;

/**
 * A Calendar component themed to match the form's FieldInput style.
 * Uses theme.secondary for selected day & nav, theme.tertiary for muted text,
 * and theme.accent for the background.
 */
function ThemedCalendar({ className, classNames, showOutsideDays = true, ...props }: ThemedCalendarProps) {
    const { theme } = useFormState();

    const secondaryColor = theme?.secondary || '';
    const tertiaryColor = theme?.tertiary || '';
    const accentColor = theme?.accent || '';

    return (
        <DayPicker
            showOutsideDays={showOutsideDays}
            className={cn('p-3', className)}
            style={{ background: accentColor }}
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
                month_grid: 'w-full border-collapse space-y-1',
                weekdays: 'flex',
                weekday: 'rounded-md w-9 font-normal text-[0.8rem]',
                week: 'flex w-full mt-2',
                // Modifier flags (selected/today/outside/...) and the aria-selected
                // attribute land on this cell in react-day-picker v10, not on
                // day_button, so the aria-selected variant below stays here.
                day: 'h-9 w-9 text-center text-sm p-0 relative aria-selected:opacity-100 focus-within:relative focus-within:z-20',
                day_button: 'h-9 w-9 rounded p-0 font-normal',
                selected: '',
                today: 'rounded',
                outside: 'opacity-50 aria-selected:opacity-30',
                disabled: 'opacity-50',
                range_middle: '',
                hidden: 'invisible',
                ...classNames
            }}
            styles={{
                caption_label: { color: secondaryColor },
                weekday: { color: tertiaryColor },
                day_button: { color: secondaryColor },
                button_previous: { color: secondaryColor },
                button_next: { color: secondaryColor }
            }}
            modifiersStyles={{
                selected: {
                    background: secondaryColor,
                    color: accentColor || '#fff'
                },
                today: {
                    background: tertiaryColor ? `${tertiaryColor}33` : undefined,
                    color: secondaryColor
                }
            }}
            components={{
                Chevron: ({ orientation, ...props }) =>
                    orientation === 'left' ? (
                        <ChevronLeft className="h-4 w-4" style={{ color: secondaryColor }} {...props} />
                    ) : (
                        <ChevronRight className="h-4 w-4" style={{ color: secondaryColor }} {...props} />
                    )
            }}
            {...props}
        />
    );
}

ThemedCalendar.displayName = 'ThemedCalendar';

export { ThemedCalendar };
