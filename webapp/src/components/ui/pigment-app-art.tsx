import React from 'react';

import { cn } from '@app/shadcn/util/lib';
import { PIGMENT_MINT, PIGMENT_ORCHID, PIGMENT_SKY, PIGMENT_SUN, PIGMENT_TOMATO } from '@app/views/molecules/theme/pigment-art';

/**
 * Pigment's picture in the creator app: the five flat shapes of the respondent ending (circle, square, triangle,
 * half-circle, ring) around an iris disc, standing still. It sits where Daybreak's sun and hills sit (the welcome band,
 * the empty states, the publish dialog) and nowhere inside a tool. Flat opaque fills in the same pigments as the
 * ending, so shapes that touch never mix into a brown or a grey; no halo, no gradient, no motion, no text. The iris
 * disc takes the app action role (`fill-app-action`), which is iris in a Pigment scope. Decorative: hidden from
 * assistive technology.
 *
 * Two compositions, because the two places are different shapes:
 * - `panel` (640 by 148, centred, cropped to the panel's height on a phone): the empty states and the publish dialog.
 *   Every shape sits at least 20 units inside the top and bottom edge and between x 130 and x 557, so the crop on a
 *   phone never cuts one and the left corner (the publish dialog's check mark) stays empty.
 * - `band` (280 by 172, pinned to the right of the welcome band): six smaller shapes; the band keeps the text clear of
 *   it by width (welcome-band.tsx), so nothing overlaps the greeting or the button.
 */
export type PigmentAppArtVariant = 'panel' | 'band';

export default function PigmentAppArt({ variant = 'panel', className }: { variant?: PigmentAppArtVariant; className?: string }) {
    if (variant === 'band') {
        return (
            <svg viewBox="0 0 280 172" preserveAspectRatio="xMaxYMid meet" aria-hidden="true" focusable="false" data-testid="pigment-app-art" data-variant="band" className={cn('block h-full w-full', className)}>
                <path d="M30 150a24 24 0 0 1 48 0Z" fill={PIGMENT_SKY} />
                <circle cx="84" cy="58" r="15" fill={PIGMENT_TOMATO} />
                <rect x="108" y="118" width="30" height="30" rx="4" transform="rotate(14 123 133)" fill={PIGMENT_SUN} />
                <circle cx="176" cy="84" r="42" className="fill-app-action" />
                <path d="M226 148H266L246 98Z" fill={PIGMENT_MINT} />
                <circle cx="248" cy="38" r="12" fill="none" stroke={PIGMENT_ORCHID} strokeWidth="8" />
            </svg>
        );
    }
    return (
        <svg viewBox="0 0 640 148" preserveAspectRatio="xMidYMid slice" aria-hidden="true" focusable="false" data-testid="pigment-app-art" data-variant="panel" className={cn('block h-full w-full', className)}>
            <circle cx="142" cy="100" r="8" fill={PIGMENT_SUN} />
            <circle cx="196" cy="52" r="20" fill={PIGMENT_TOMATO} />
            <rect x="262" y="82" width="34" height="34" rx="5" transform="rotate(15 279 99)" fill={PIGMENT_SUN} />
            <circle cx="336" cy="74" r="42" className="fill-app-action" />
            <path d="M404 124H456L430 62Z" fill={PIGMENT_MINT} />
            <path d="M478 128a30 30 0 0 1 60 0Z" fill={PIGMENT_SKY} />
            <rect x="520" y="112" width="16" height="16" rx="3" fill={PIGMENT_TOMATO} />
            <circle cx="526" cy="46" r="17" fill="none" stroke={PIGMENT_ORCHID} strokeWidth="9" />
        </svg>
    );
}
