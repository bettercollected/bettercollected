import React from 'react';

import { formHueIndex } from '@app/lib/form-hue';
import { cn } from '@app/shadcn/util/lib';

// One literal class string per index, so Tailwind sees them. The colours are the app theme's
// `--form-hue-N-bg` / `--form-hue-N-ink` pairs (tailwind.css): a later theme supplies its own.
const HUE_CLASSES = ['bg-form-hue-0-bg text-form-hue-0-ink', 'bg-form-hue-1-bg text-form-hue-1-ink', 'bg-form-hue-2-bg text-form-hue-2-ink', 'bg-form-hue-3-bg text-form-hue-3-ink', 'bg-form-hue-4-bg text-form-hue-4-ink'] as const;

/** The classes of a form's tile: its tint and its ink, from its id alone. */
export function formHueClasses(formId: string | undefined | null): string {
    return HUE_CLASSES[formHueIndex(formId ?? '')];
}

/** The letter the tile shows: the first letter of the title, else "F". */
export function formInitial(title: string | undefined | null): string {
    const first = Array.from((title ?? '').trim())[0];
    return first ? first.toUpperCase() : 'F';
}

/**
 * A form's tile in lists and headers: its initial in a tint that belongs to the form (the same
 * form always has the same one), so forms tell apart at a glance. The tile is decoration (the
 * title is always beside it), hidden from assistive technology.
 */
export default function FormAvatar({ formId, title, className }: { formId: string | undefined | null; title: string | undefined | null; className?: string }) {
    return (
        <span data-testid="form-avatar" data-hue={formHueIndex(formId ?? '')} aria-hidden="true" className={cn('flex h-11 w-11 shrink-0 items-center justify-center rounded-md text-sm font-semibold', formHueClasses(formId), className)}>
            {formInitial(title)}
        </span>
    );
}
