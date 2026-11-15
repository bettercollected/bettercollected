import React, { useId } from 'react';

import DaybreakArt from '@app/components/ui/daybreak-art';
import { cn } from '@app/shadcn/util/lib';

interface EmptyStateProps {
    title: string;
    /** One plain sentence: what is empty and what will fill it. */
    description?: string;
    /** The one next step (a primary button or a link-styled button); omitted when there is none to take. */
    action?: React.ReactNode;
    /** The sun-and-hills motif in a tinted panel. Off for a search or a filter with no match: a clear line and a way back is enough. */
    illustration?: boolean;
    /** The title's heading level; pages that already have an h1 pass 2 (the default) or 3. A page whose card is its whole content (the first run) passes 1. */
    headingLevel?: 1 | 2 | 3;
    className?: string;
}

/**
 * The one empty state of the creator app: a white card with the motif in a tinted panel, a title,
 * one sentence and at most one primary action. It tells people nothing is wrong and what to do
 * (DESIGN.md §1, empty states).
 */
export default function EmptyState({ title, description, action, illustration = true, headingLevel = 2, className }: EmptyStateProps) {
    const id = useId();
    const Heading = `h${headingLevel}` as 'h1' | 'h2' | 'h3';
    return (
        <section aria-labelledby={id} data-testid="empty-state" data-illustration={illustration ? 'true' : 'false'} className={cn('flex w-full max-w-[640px] flex-col overflow-hidden rounded border border-hairline-strong bg-surface', className)}>
            {illustration && (
                <div className="h-[104px] bg-brand-tint sm:h-[148px]">
                    <DaybreakArt />
                </div>
            )}
            <div className="flex flex-col gap-1.5 p-5 sm:p-6">
                <Heading id={id} className="m-0 text-lg leading-snug font-semibold tracking-title-sm text-ink">
                    {title}
                </Heading>
                {description && <p className="m-0 max-w-[56ch] text-sm leading-relaxed text-copy">{description}</p>}
                {action && <div className="mt-3 flex flex-wrap items-center gap-3">{action}</div>}
            </div>
        </section>
    );
}
