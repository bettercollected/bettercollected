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
                month: 'space-y-4',
                caption: 'flex justify-center pt-1 relative items-center',
                caption_label: 'text-sm font-medium',
                nav: 'space-x-1 flex items-center',
                nav_button: cn('h-7 w-7 bg-transparent p-0 opacity-50 hover:opacity-100'),
                nav_button_previous: cn('absolute left-1 opacity-50', 'hover:!opacity-50 disabled:cursor-not-allowed'),
                nav_button_next: 'absolute right-1',
                table: 'w-full border-collapse space-y-1',
                head_row: 'flex',
                head_cell: 'rounded-md w-9 font-normal text-[0.8rem]',
                row: 'flex w-full mt-2',
                cell: 'h-9 w-9 text-center text-sm p-0 relative focus-within:relative focus-within:z-20',
                day: cn('h-9 w-9 p-0 font-normal aria-selected:opacity-100 rounded'),
                day_range_end: 'day-range-end',
                day_selected: '',
                day_today: 'rounded',
                day_outside: 'day-outside opacity-50 aria-selected:opacity-30',
                day_disabled: 'opacity-50',
                day_range_middle: '',
                day_hidden: 'invisible',
                ...classNames
            }}
            styles={{
                caption_label: { color: secondaryColor },
                head_cell: { color: tertiaryColor },
                day: { color: secondaryColor },
                nav_button_previous: { color: secondaryColor },
                nav_button_next: { color: secondaryColor }
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
                IconLeft: () => <ChevronLeft className="h-4 w-4" style={{ color: secondaryColor }} />,
                IconRight: () => <ChevronRight className="h-4 w-4" style={{ color: secondaryColor }} />
            }}
            {...props}
        />
    );
}

ThemedCalendar.displayName = 'ThemedCalendar';

export { ThemedCalendar };
