'use client';

import { ReactNode, useId, useState } from 'react';

import { Switch } from '@app/shadcn/components/ui/switch';
import { cn } from '@app/shadcn/util/lib';

/** A titled group of settings in the inspector (Basics, Answer rules, …). */
export function InspectorSection({ title, children, className }: { title: string; children: ReactNode; className?: string }) {
    const id = useId();
    return (
        <section aria-labelledby={id} className={cn('flex flex-col gap-4 border-b border-black-300 px-4 py-4 last:border-b-0', className)}>
            <h3 id={id} className="text-xs font-semibold tracking-wide text-black-600 uppercase">
                {title}
            </h3>
            {children}
        </section>
    );
}

/** An on/off setting: the label names the switch, the hint describes it. */
export function SettingSwitch({ label, checked, onCheckedChange, hint, disabled }: { label: string; checked: boolean; onCheckedChange: (checked: boolean) => void; hint?: ReactNode; disabled?: boolean }) {
    const id = useId();
    return (
        <div className="flex w-full flex-col gap-1">
            <div className="flex w-full items-center justify-between gap-4">
                <label htmlFor={id} className="text-xs text-black-700">
                    {label}
                </label>
                <Switch id={id} checked={checked} disabled={disabled} onCheckedChange={onCheckedChange} aria-describedby={hint ? `${id}-hint` : undefined} />
            </div>
            {hint && (
                <p id={`${id}-hint`} className="text-[11px] leading-relaxed text-black-600">
                    {hint}
                </p>
            )}
        </div>
    );
}

/**
 * A number setting that may be left empty (no limit). Keeps what is being
 * typed ("-", "1.") while it is not yet a number, and reports the parsed
 * value, or undefined when empty.
 */
export function NumberSetting({
    label,
    value,
    onChange,
    min,
    max,
    step = 1,
    integer = true,
    placeholder = 'No limit',
    invalid
}: {
    label: string;
    value: number | undefined;
    onChange: (value: number | undefined) => void;
    min?: number;
    max?: number;
    step?: number | 'any';
    integer?: boolean;
    placeholder?: string;
    invalid?: boolean;
}) {
    const id = useId();
    const [draft, setDraft] = useState(value === undefined || value === null ? '' : String(value));
    // A change from elsewhere (undo, another control) replaces the draft,
    // unless the draft already says the same number.
    const [shown, setShown] = useState(value);
    if (shown !== value) {
        setShown(value);
        const parsed = draft.trim() === '' ? undefined : Number(draft);
        if (parsed !== value) setDraft(value === undefined || value === null ? '' : String(value));
    }
    return (
        <div className="flex min-w-0 flex-1 flex-col gap-1">
            <label htmlFor={id} className="text-xs text-black-700">
                {label}
            </label>
            <input
                id={id}
                type="number"
                inputMode={integer ? 'numeric' : 'decimal'}
                min={min}
                max={max}
                step={step}
                value={draft}
                placeholder={placeholder}
                aria-invalid={invalid || undefined}
                onChange={(event) => {
                    const text = event.target.value;
                    setDraft(text);
                    if (text.trim() === '') return onChange(undefined);
                    const parsed = Number(text);
                    if (!Number.isFinite(parsed)) return;
                    onChange(integer ? Math.trunc(parsed) : parsed);
                }}
                className={cn('h-8 w-full rounded border bg-white px-2 text-xs tabular-nums', invalid ? 'border-amber-500' : 'border-control focus:border-brand-500')}
            />
        </div>
    );
}
