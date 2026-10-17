'use client';

import { ReactNode, useEffect, useState } from 'react';

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
 * On the welcome and ending pages the account control shares the row, on the
 * column's right edge (`action`), so it needs no row of its own.
 *
 * The strip's height is fixed, so the page never moves when the image
 * arrives, and it is marked `data-fit-reserve`: the privacy panel's "Start
 * stays in view" check takes it off the room the page has (utils/panel-fit.ts).
 * The image keeps its proportions and is never drawn larger than it is.
 * Leaflet: a white strip with no rule of its own (the next row's rule, or the
 * section bar, closes it). Other styles: the theme's page colour with a 1px rule.
 */
export default function FormLogoStrip({
    logo,
    theme,
    layout,
    size = 'page',
    action,
    className
}: {
    logo: ResolvedFormLogo;
    theme?: Partial<FormTheme>;
    layout?: FormSlideLayout | null;
    size?: 'cover' | 'page';
    /** The respondent's account control, right-aligned in the logo's row. */
    action?: ReactNode;
    className?: string;
}) {
    const [failed, setFailed] = useState(false);
    useEffect(() => setFailed(false), [logo.src]);
    // An image that does not load leaves no empty band, unless the row also
    // holds the account control.
    if (failed && !action) return null;

    const leaflet = styleTokens(theme?.style).key === 'leaflet';
    const ground = leaflet ? '#FFFFFF' : theme?.accent || '#FFFFFF';
    const cover = size === 'cover';
    const centred = logo.position === 'center';
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
                <div className={cn(FORM_COLUMN, columnPlacementClass(layout), 'relative flex h-full items-center gap-3')}>
                    {/* The logo's room: the logo shrinks within it and never runs
                        under the control. Centred, the control's width stays free
                        on both sides, so the logo stays centred on the column. */}
                    <div className={cn('flex h-full min-w-0 flex-1 items-center', centred ? 'justify-center' : 'justify-start', centred && action && 'px-[72px]')} data-testid="form-logo-room">
                        {!failed && (
                            // eslint-disable-next-line @next/next/no-img-element -- served as is from our own storage; next/image would re-encode it through the app
                            <img
                                src={logo.src}
                                alt={logo.alt}
                                // Natural size at most: max-h/max-w only ever shrink it.
                                className={cn('block h-auto w-auto min-w-0 object-contain', cover ? 'max-h-14 max-w-[min(100%,240px)] sm:max-h-16 sm:max-w-[min(100%,320px)]' : 'max-h-10 max-w-[min(100%,200px)] sm:max-h-12 sm:max-w-[min(100%,260px)]')}
                                decoding="async"
                                referrerPolicy="no-referrer"
                                onError={() => setFailed(true)}
                                data-testid="form-logo"
                            />
                        )}
                    </div>
                    {action && (
                        <div className={cn('flex shrink-0 items-center', centred && 'absolute top-1/2 right-0 -translate-y-1/2')} data-testid="form-logo-action">
                            {action}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
