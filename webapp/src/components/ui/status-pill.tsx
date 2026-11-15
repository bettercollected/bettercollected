import React from 'react';

import { cn } from '@app/shadcn/util/lib';

export type StatusTone = 'ok' | 'warn' | 'bad' | 'info' | 'neutral';

// Text and tint pairs from the Daybreak status tokens (DESIGN.md §1): each is at least 4.5:1.
const TONES: Record<StatusTone, string> = {
    ok: 'bg-ok-tint text-ok',
    warn: 'bg-warn-tint text-warn',
    bad: 'bg-bad-tint text-bad',
    info: 'bg-info-tint text-info',
    neutral: 'bg-sunken text-ink-muted'
};

/**
 * A status as a dot and a word. The colour is the second cue, never the only one:
 * the word says the state, and the dot takes the text colour, so it reads wherever
 * the word does.
 */
export function StatusPill({ tone, children, className }: { tone: StatusTone; children: React.ReactNode; className?: string }) {
    return (
        <span className={cn('inline-flex w-fit shrink-0 items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs leading-4 font-semibold', TONES[tone], className)}>
            <span aria-hidden="true" className="h-1.5 w-1.5 shrink-0 rounded-full bg-current" />
            {children}
        </span>
    );
}
