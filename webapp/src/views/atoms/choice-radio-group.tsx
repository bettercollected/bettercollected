import { AriaAttributes, KeyboardEvent, ReactNode, useRef } from 'react';

import { FormTheme } from '@app/constants/theme';

import { ChoiceContent, choiceRowStyle, optionIndexForKey, optionKeys, showsOptionKeys } from './choice';

export interface RadioOption<T> {
    value: T;
    label: ReactNode;
    key: string;
    /** The label's language, when it is not the page's. */
    lang?: string;
    /** Its key letter, when not the next of A, B, C… (see initialKeys). */
    keyHint?: string;
}

/**
 * A single-answer list as a WAI-ARIA radio group: one tab stop (the chosen
 * option, else the first), arrow keys move and choose, Space chooses, and
 * the group is named by the question (`labelledBy`, or `labelProps` for the
 * question's full name, description and state). Every option is the
 * shared choice row (atoms/choice.tsx).
 *
 * On a theme that shows option keys (showsOptionKeys), each option carries
 * its letter, and pressing a letter while the group has focus chooses that
 * option and moves focus to it.
 *
 * `onChange` says whether the choice came from the keyboard (an arrow key
 * or a letter), so callers can skip moving on to the next question while
 * the respondent is still at the options.
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
    onChange: (value: T, meta: { viaKeys: boolean }) => void;
    theme?: Partial<FormTheme>;
    labelledBy?: string;
    labelProps?: AriaAttributes;
    className?: string;
}) {
    const refs = useRef<Array<HTMLButtonElement | null>>([]);
    const selectedIndex = options.findIndex((option) => option.value === value);
    const tabStop = selectedIndex >= 0 ? selectedIndex : 0;
    const letters = optionKeys(options.length);
    const keys = showsOptionKeys(theme) ? options.map((option, index) => option.keyHint ?? letters[index]) : [];

    const choose = (event: KeyboardEvent<HTMLButtonElement>, index: number) => {
        event.preventDefault();
        refs.current[index]?.focus();
        onChange(options[index].value, { viaKeys: true });
    };

    const onKeyDown = (event: KeyboardEvent<HTMLButtonElement>, index: number) => {
        const lettered = optionIndexForKey(event, keys);
        if (lettered >= 0) return choose(event, lettered);
        const step = event.key === 'ArrowDown' || event.key === 'ArrowRight' ? 1 : event.key === 'ArrowUp' || event.key === 'ArrowLeft' ? -1 : 0;
        if (!step || options.length === 0) return;
        choose(event, (index + step + options.length) % options.length);
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
                        aria-keyshortcuts={keys[index]}
                        data-option-key={keys[index]}
                        onClick={() => onChange(option.value, { viaKeys: false })}
                        onKeyDown={(event) => onKeyDown(event, index)}
                        className={row.className}
                        style={row.style}
                    >
                        <ChoiceContent kind="radio" selected={checked} theme={theme} solid={row.solid} lang={option.lang} keyHint={keys[index]}>
                            {option.label}
                        </ChoiceContent>
                    </button>
                );
            })}
        </div>
    );
}
