import React from 'react';

import { cn } from '@app/shadcn/util/lib';

export const inputClass =
    'h-10 w-full rounded-md border border-control bg-white px-3.5 py-0 text-sm text-black-900 outline-hidden transition duration-150 placeholder:text-black-600 focus:border-brand-500 aria-[invalid=true]:border-[#C43D3D] disabled:bg-black-200';

interface FieldProps {
    id: string;
    label: string;
    hint?: React.ReactNode;
    error?: string | null;
    children: (props: { id: string; 'aria-invalid': boolean; 'aria-describedby'?: string }) => React.ReactNode;
}

/**
 * A labelled field whose hint and error are tied to the control
 * (`aria-describedby`), so a screen reader reads them with it.
 */
export function Field({ id, label, hint, error, children }: FieldProps) {
    const hintId = hint ? `${id}-hint` : undefined;
    const errorId = error ? `${id}-error` : undefined;
    const describedBy = [hintId, errorId].filter(Boolean).join(' ') || undefined;
    return (
        <div className="flex flex-col gap-1.5">
            <label htmlFor={id} className="text-sm font-medium text-black-900">
                {label}
            </label>
            {children({ id, 'aria-invalid': !!error, 'aria-describedby': describedBy })}
            {hint && (
                <p id={hintId} className="text-xs leading-relaxed text-black-600">
                    {hint}
                </p>
            )}
            {error && (
                <p id={errorId} className={cn('text-xs font-medium text-[#A83434]')}>
                    {error}
                </p>
            )}
        </div>
    );
}
