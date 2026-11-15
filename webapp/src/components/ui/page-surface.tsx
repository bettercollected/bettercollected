import React from 'react';

import { cn } from '@app/shadcn/util/lib';

/**
 * The one surface of the creator app's pages, now that their ground is the periwinkle canvas (`bg-canvas`) and no
 * longer white. The form pages (components/form/form-page.tsx) and the workspace pages read these, so a card is the
 * same card everywhere:
 *
 *  - `PAGE_CARD`: a white card with the strong hairline edge and a radius, 16 px inside on a phone and 24 px from `sm`
 *    up. Content that was laid out for a white page (text, inputs, radio rows, tables) sits in one, never straight on
 *    the canvas.
 *  - `PAGE_ROWS`: a card of rows with one divider (the hairline) between them. The padding is the card's, so a row's
 *    own top and bottom padding gives the rhythm and the divider runs edge to edge.
 *  - `PageSurface`: a card that holds a whole page's content, with one rhythm between its parts. `narrow` keeps
 *    settings-like pages (text and inputs) to a 760 px column; pages of tables and grids take the whole width.
 */
export const PAGE_CARD = 'rounded-lg border border-hairline-strong bg-surface p-4 sm:p-6';
export const PAGE_ROWS = 'flex flex-col divide-y divide-hairline-strong rounded-lg border border-hairline-strong bg-surface px-4 sm:px-6';

export function PageSurface({ children, className, narrow = false }: { children: React.ReactNode; className?: string; narrow?: boolean }) {
    return <div className={cn(PAGE_CARD, 'flex w-full min-w-0 flex-col gap-6', narrow && 'max-w-[760px]', className)}>{children}</div>;
}
