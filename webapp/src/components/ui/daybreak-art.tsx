import React from 'react';

import { cn } from '@app/shadcn/util/lib';

/**
 * The Daybreak motif: a flat sun over two hills, with one small coral spark beside the sun, well away from any text. Inline SVG, drawn
 * here (nothing is fetched), in the app theme's own colours: the blue action colour for the hills
 * and the sun accent for the sun. It sits in the welcome band and in the empty states, and
 * nowhere inside the builder canvas or a table. Decorative: hidden from assistive technology.
 */
export default function DaybreakArt({ className, spark = true }: { className?: string; /** Off where a control sits at the corner of the panel (the dialog's close button): a coral dot beside it reads as a notification. */ spark?: boolean }) {
    return (
        <svg viewBox="-360 0 1000 148" preserveAspectRatio="xMaxYMax slice" aria-hidden="true" focusable="false" className={cn('block h-full w-full', className)}>
            <circle cx="460" cy="82" r="59" className="fill-sun/35" />
            <circle cx="460" cy="82" r="44" className="fill-sun" />
            <path d="M-360 148 V126 C-250 128 -110 96 0 115 C76 74 166 76 256 109 S396 140 499 103 S588 91 652 88 V148 Z" className="fill-app-action/15" />
            <path d="M-360 148 V140 C-250 142 -120 122 0 133 C128 106 294 124 422 142 S576 150 640 124 V148 Z" className="fill-app-action/30" />
            {spark && <circle cx="575" cy="38" r="6" className="fill-coral" />}
        </svg>
    );
}
