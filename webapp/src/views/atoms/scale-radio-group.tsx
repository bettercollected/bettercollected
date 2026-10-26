import { AriaAttributes, Fragment, KeyboardEvent, ReactNode } from 'react';

/** What a cell of a scale needs to be one radio of the group (spread onto a button). */
export interface ScaleCellProps {
    role: 'radio';
    'aria-checked': boolean;
    tabIndex: number;
    'aria-keyshortcuts'?: string;
    'data-scale-value': number;
    onClick: () => void;
    onKeyDown: (event: KeyboardEvent<HTMLButtonElement>) => void;
}

/**
 * The value a key names within `values`: Home and End the first and last,
 * the arrows the neighbour (wrapping; the horizontal arrows follow the
 * reading direction), a digit the value written with it. Only a plain key
 * counts (no Ctrl, Alt or Meta, so browser and screen reader shortcuts pass
 * through). `from` is the focused cell's index. Returns an index or -1.
 */
export function scaleIndexForKey(event: Pick<KeyboardEvent<HTMLElement>, 'key' | 'ctrlKey' | 'altKey' | 'metaKey'>, values: number[], from: number, rtl = false): number {
    if (event.ctrlKey || event.altKey || event.metaKey || values.length === 0) return -1;
    const { key } = event;
    if (key === 'Home') return 0;
    if (key === 'End') return values.length - 1;
    const forward = rtl ? 'ArrowLeft' : 'ArrowRight';
    const backward = rtl ? 'ArrowRight' : 'ArrowLeft';
    const step = key === 'ArrowDown' || key === forward ? 1 : key === 'ArrowUp' || key === backward ? -1 : 0;
    if (step) return (from + step + values.length) % values.length;
    if (/^[0-9]$/.test(key)) return values.indexOf(Number(key));
    return -1;
}

/**
 * A scale answered with one value (a star rating, a number scale) as a
 * WAI-ARIA radio group: one tab stop (the chosen value, else the first),
 * arrow keys, Home and End move and choose, and a digit chooses the value
 * written with it while focus is inside the group (the keys only act on the
 * focused group, never in a text field: WCAG 2.1.4). The group is named by
 * the question (`labelProps`).
 *
 * `onChange` says whether the choice came from the keyboard, so callers can
 * skip moving on to the next question while the respondent is still at the
 * scale (as the option lists do). `disabled` (the builder canvas) keeps the
 * radios but takes no key.
 */
export default function ScaleRadioGroup({
    values,
    value,
    onChange,
    labelProps,
    className,
    disabled = false,
    children
}: {
    values: number[];
    value: number | null | undefined;
    onChange: (value: number, meta: { viaKeys: boolean }) => void;
    labelProps?: AriaAttributes;
    className?: string;
    disabled?: boolean;
    children: (item: number, cell: ScaleCellProps, meta: { checked: boolean; index: number }) => ReactNode;
}) {
    const selectedIndex = values.findIndex((item) => item === value);
    const tabStop = selectedIndex >= 0 ? selectedIndex : 0;

    const onKeyDown = (event: KeyboardEvent<HTMLButtonElement>, index: number) => {
        if (disabled) return;
        const rtl = typeof getComputedStyle === 'function' && getComputedStyle(event.currentTarget).direction === 'rtl';
        const next = scaleIndexForKey(event, values, index, rtl);
        if (next < 0) return;
        event.preventDefault();
        event.currentTarget.closest('[role="radiogroup"]')?.querySelector<HTMLElement>(`[data-scale-value="${values[next]}"]`)?.focus();
        onChange(values[next], { viaKeys: true });
    };

    return (
        <div role="radiogroup" {...labelProps} className={className}>
            {values.map((item, index) => (
                <Fragment key={item}>
                    {children(
                        item,
                        {
                            role: 'radio',
                            'aria-checked': index === selectedIndex,
                            tabIndex: index === tabStop ? 0 : -1,
                            'aria-keyshortcuts': item >= 0 && item <= 9 && !disabled ? String(item) : undefined,
                            'data-scale-value': item,
                            onClick: () => !disabled && onChange(item, { viaKeys: false }),
                            onKeyDown: (event) => onKeyDown(event, index)
                        },
                        { checked: index === selectedIndex, index }
                    )}
                </Fragment>
            ))}
        </div>
    );
}
