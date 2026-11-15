import React from 'react';

import { cn } from '@app/shadcn/util/lib';

/**
 * The page pattern of a form's pages (Share, Settings and the pages that read like them), on the canvas of the form
 * shell. The shell gives every page the same gutters (`main` in form-shell.tsx); these give them the same width and the
 * same surface:
 *
 *  - `FormPage`: the column. At most 760 px wide, with one rhythm between its parts. Wide pages (a table of responses)
 *    do not use it and take the whole width.
 *  - `FORM_CARD`: a white card with the strong hairline edge, 16 px inside on a phone and 24 px from `sm` up. Content
 *    that was laid out for a white page (text, inputs, radio rows) sits in one, never straight on the canvas.
 *  - `FORM_ROWS`: a card of rows, one divider (the hairline) between them. The padding is the card's, so a row's own
 *    top and bottom padding gives the rhythm and the divider runs edge to edge.
 */
export const FORM_CARD = 'rounded-lg border border-hairline-strong bg-surface p-4 sm:p-6';
export const FORM_ROWS = 'flex flex-col divide-y divide-hairline-strong rounded-lg border border-hairline-strong bg-surface px-4 sm:px-6';

export function FormPage({ children, className }: { children: React.ReactNode; className?: string }) {
    return <div className={cn('flex w-full min-w-0 max-w-[760px] flex-col gap-8 pb-6', className)}>{children}</div>;
}
