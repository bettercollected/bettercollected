import React from 'react';

import { cn } from '@app/shadcn/util/lib';

/**
 * "Something is waiting for you": a number in coral tint with coral ink. It is always the number
 * itself (never a bare dot or colour), and the full phrase ("2 waiting for you") is the accessible
 * name, so the colour is never the only cue. Nothing renders for zero. It is information, not
 * urgency: no pulse, no red.
 */
export function CountBadge({ count, label, className }: { count: number; /** The whole phrase, with the number in it. */ label: string; className?: string }) {
    if (!(count > 0)) return null;
    return (
        <span data-testid="count-badge" className={cn('inline-flex min-w-5 shrink-0 items-center justify-center rounded-full bg-coral-tint px-1.5 text-xs leading-5 font-semibold text-coral-ink tabular-nums', className)}>
            <span aria-hidden="true">{count > 99 ? '99+' : count}</span>
            <span className="sr-only">{label}</span>
        </span>
    );
}
