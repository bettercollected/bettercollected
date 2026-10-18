import { AriaAttributes, KeyboardEvent, ReactNode, useRef } from 'react';

import { FormTheme } from '@app/constants/theme';

import { ChoiceContent, choiceRowStyle } from './choice';

export interface RadioOption<T> {
    value: T;
    label: ReactNode;
    key: string;
}

/**
 * A single-answer list as a WAI-ARIA radio group: one tab stop (the chosen
 * option, else the first), arrow keys move and choose, Space chooses, and
 * the group is named by the question (`labelledBy`, or `labelProps` for the
 * question's full name, description and state). Every option is the
 * shared choice row (atoms/choice.tsx).
 *
 * `onChange` says whether the choice came from the arrow keys, so callers
 * can skip moving on to the next question while the respondent is still
 * stepping through the options.
 */
export default function ChoiceRadioGroup<T>({
    options,
    value,
    onChange,
    theme,
    labelledBy,
    labelProps,
    className
}: {
    options: Array<RadioOption<T>>;
    value: T | null | undefined;
    onChange: (value: T, meta: { viaArrowKeys: boolean }) => void;
    theme?: Partial<FormTheme>;
    labelledBy?: string;
    labelProps?: AriaAttributes;
    className?: string;
}) {
    const refs = useRef<Array<HTMLButtonElement | null>>([]);
    const selectedIndex = options.findIndex((option) => option.value === value);
    const tabStop = selectedIndex >= 0 ? selectedIndex : 0;

    const onKeyDown = (event: KeyboardEvent<HTMLButtonElement>, index: number) => {
        const step = event.key === 'ArrowDown' || event.key === 'ArrowRight' ? 1 : event.key === 'ArrowUp' || event.key === 'ArrowLeft' ? -1 : 0;
        if (!step || options.length === 0) return;
        event.preventDefault();
        const next = (index + step + options.length) % options.length;
        refs.current[next]?.focus();
        onChange(options[next].value, { viaArrowKeys: true });
    };

    return (
        <div role="radiogroup" aria-labelledby={labelledBy} {...labelProps} className={className}>
            {options.map((option, index) => {
                const checked = index === selectedIndex;
                const row = choiceRowStyle(theme, checked);
                return (
                    <button
                        key={option.key}
                        ref={(element) => {
                            refs.current[index] = element;
                        }}
                        type="button"
                        role="radio"
                        aria-checked={checked}
                        tabIndex={index === tabStop ? 0 : -1}
                        onClick={() => onChange(option.value, { viaArrowKeys: false })}
                        onKeyDown={(event) => onKeyDown(event, index)}
                        className={row.className}
                        style={row.style}
                    >
                        <ChoiceContent kind="radio" selected={checked} theme={theme} solid={row.solid}>
                            {option.label}
                        </ChoiceContent>
                    </button>
                );
            })}
        </div>
    );
}
