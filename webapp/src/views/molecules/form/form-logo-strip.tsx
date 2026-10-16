'use client';

import { useEffect, useState } from 'react';

import { FormTheme } from '@app/constants/theme';
import { FormSlideLayout } from '@app/models/enums/form';
import { cn } from '@app/shadcn/util/lib';
import { ResolvedFormLogo } from '@app/utils/form-logo';
import { leafletColours, styleTokens } from '@app/views/molecules/theme/theme-shared';
import { FORM_COLUMN, FORM_GUTTER, columnPlacementClass } from '@app/views/organism/layout/form-column';

/**
 * The organisation logo strip at the very top of a respondent page
 * (DESIGN.md §9, "Organisation logo"): a calm band on the page's own ground,
 * the logo on the form column's left edge or centred on it.
 *
 * - `cover` (welcome page): the logo up to 56px tall on phones, 64px from `sm`.
 * - `page` (question and ending pages): up to 40px, 48px from `sm`.
 *
 * The strip's height is fixed, so the page never moves when the image
 * arrives, and it is marked `data-fit-reserve`: the privacy panel's "Start
 * stays in view" check takes it off the room the page has (utils/panel-fit.ts).
 * The image keeps its proportions and is never drawn larger than it is.
 * Leaflet: a white strip with no rule of its own; the 56px top row's rule
 * right under it closes the masthead. Other styles: the theme's page colour
 * with a 1px rule.
 */
export default function FormLogoStrip({ logo, theme, layout, size = 'page', className }: { logo: ResolvedFormLogo; theme?: Partial<FormTheme>; layout?: FormSlideLayout | null; size?: 'cover' | 'page'; className?: string }) {
    const [failed, setFailed] = useState(false);
    useEffect(() => setFailed(false), [logo.src]);
    if (failed) return null;

    const leaflet = styleTokens(theme?.style).key === 'leaflet';
    const ground = leaflet ? '#FFFFFF' : theme?.accent || '#FFFFFF';
    const cover = size === 'cover';
    return (
        <div
            className={cn('relative z-20 w-full shrink-0', cover ? 'h-20 sm:h-24' : 'h-16 sm:h-[72px]', !leaflet && 'border-b', className)}
            style={{ background: ground, ...(leaflet ? {} : { borderColor: leafletColours(theme).rule }) }}
            data-fit-reserve
            data-testid="form-logo-strip"
            data-logo-position={logo.position}
            data-logo-size={size}
        >
            <div className={cn(FORM_GUTTER, 'flex h-full w-full items-center')}>
                <div className={cn(FORM_COLUMN, columnPlacementClass(layout), 'flex h-full items-center', logo.position === 'center' ? 'justify-center' : 'justify-start')}>
                    {/* eslint-disable-next-line @next/next/no-img-element -- served as is from our own storage; next/image would re-encode it through the app */}
                    <img
                        src={logo.src}
                        alt={logo.alt}
                        // Natural size at most: max-h/max-w only ever shrink it.
                        className={cn('block h-auto w-auto object-contain', cover ? 'max-h-14 max-w-[min(100%,240px)] sm:max-h-16 sm:max-w-[320px]' : 'max-h-10 max-w-[min(100%,200px)] sm:max-h-12 sm:max-w-[260px]')}
                        decoding="async"
                        referrerPolicy="no-referrer"
                        onError={() => setFailed(true)}
                        data-testid="form-logo"
                    />
                </div>
            </div>
        </div>
    );
}
