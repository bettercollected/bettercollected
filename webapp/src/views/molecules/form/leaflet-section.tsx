import { ReactNode } from 'react';

import { leafletSerif } from '@app/assets/fonts/leaflet-serif';
import { FormTheme } from '@app/constants/theme';
import useRespondentLanguage from '@app/lib/hooks/use-respondent-language';
import { StandardFormFieldDto } from '@app/models/dtos/form';
import { FormSlideLayout } from '@app/models/enums/form';
import { cn } from '@app/shadcn/util/lib';
import { leafletSection } from '@app/utils/leaflet-sections';
import { contrast, leafletColours } from '@app/views/molecules/theme/theme-shared';
import { FORM_COLUMN, columnPlacementClass, isLeftAligned } from '@app/views/organism/layout/form-column';

/**
 * Whether a page's margin numbers may hang outside the text measure: only on
 * full-width, centred pages, and only when the page is wide enough (the
 * `@min-[880px]/page` variants). Left-aligned and image layouts keep the
 * numbers in their 34px column.
 */
export function leafletNumbersHang(layout?: FormSlideLayout | null) {
    return !isLeftAligned(layout) && (!layout || layout === FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND || layout === FormSlideLayout.SINGLE_COLUMN_IMAGE_BACKGROUND);
}

// Bleeds out of the page gutter (form-column.ts FORM_GUTTER) to the page edges.
const BLEED = '-mx-5 px-5 sm:-mx-8 sm:px-8';

/**
 * The Leaflet style's section bar: a full-width band in the theme's
 * secondary, carrying the serif section numeral (in the margin column) and
 * the section title in white. Without a numeral it is the cover of the
 * welcome and ending pages, with a larger title.
 */
export function LeafletSectionBar({
    theme,
    numeral,
    title,
    fullTitle,
    layout,
    headingLevel = 2,
    className
}: {
    theme?: Partial<FormTheme>;
    numeral?: number | string;
    title: ReactNode;
    /** The unshortened title, read out instead of a shortened `title`. */
    fullTitle?: string;
    layout?: FormSlideLayout | null;
    headingLevel?: 1 | 2;
    className?: string;
}) {
    const hang = leafletNumbersHang(layout);
    const Heading = headingLevel === 1 ? 'h1' : 'h2';
    const serif = { fontFamily: leafletSerif.style.fontFamily, fontWeight: 600 };
    return (
        <div className={cn(BLEED, numeral === undefined ? 'py-6 sm:py-8' : 'py-3.5', className)} style={{ background: theme?.secondary, color: '#ffffff' }} data-testid="leaflet-section-bar">
            <div className={cn(FORM_COLUMN, columnPlacementClass(layout), 'relative')}>
                {numeral === undefined ? (
                    <Heading className="max-w-[24ch] text-[30px] leading-[1.15] tracking-[-0.01em] text-balance [overflow-wrap:anywhere] sm:text-[38px]" style={serif}>
                        {title}
                    </Heading>
                ) : (
                    <Heading className={cn('grid grid-cols-[var(--leaflet-margin,34px)_minmax(0,1fr)] items-baseline', hang && '@min-[880px]/page:block')} style={serif}>
                        <span
                            className={cn('text-[28px] leading-none tabular-nums', hang && '@min-[880px]/page:absolute @min-[880px]/page:top-0 @min-[880px]/page:-left-16 @min-[880px]/page:w-12 @min-[880px]/page:text-right')}
                            data-testid="leaflet-section-numeral"
                        >
                            {numeral}
                        </span>
                        <span className="text-[22px] leading-[1.25] text-balance [overflow-wrap:anywhere]">
                            <ShortLabel short={title} full={fullTitle} />
                        </span>
                    </Heading>
                )}
            </div>
        </div>
    );
}

/** A shortened label on screen, its full text for assistive tech. */
function ShortLabel({ short, full }: { short: ReactNode; full?: string }) {
    if (!full || full === short) return <>{short}</>;
    return (
        <>
            <span aria-hidden="true" title={full}>
                {short}
            </span>
            <span className="sr-only">{full}</span>
        </>
    );
}

/** The pale intro band under a section bar (a tint of the secondary, 7:1 for the ink). */
export function LeafletIntroBand({ theme, layout, children, className }: { theme?: Partial<FormTheme>; layout?: FormSlideLayout | null; children: ReactNode; className?: string }) {
    return (
        <div className={cn(BLEED, 'py-4 text-base leading-[1.6]', className)} style={{ background: leafletColours(theme).band, color: theme?.primary }} data-testid="leaflet-intro-band">
            <div className={cn(FORM_COLUMN, columnPlacementClass(layout), '[&_p]:leading-[1.6]')}>{children}</div>
        </div>
    );
}

/** The 56px top row with its hairline, as on the question pages (where it holds Back and the page count). */
export function LeafletTopRule({ theme }: { theme?: Partial<FormTheme> }) {
    return <div className="-mx-5 h-14 border-b sm:-mx-8" style={{ borderColor: leafletColours(theme).rule }} aria-hidden="true" />;
}

/**
 * The cover's contents: every page's section number and the title its
 * section bar shows (its own heading, else its first question, else
 * "Section n"), so the list matches the pages.
 */
export function LeafletContents({ pages, theme }: { pages: ReadonlyArray<StandardFormFieldDto> | undefined; theme?: Partial<FormTheme> }) {
    const { t } = useRespondentLanguage();
    const sections = (pages ?? []).map((page, position) => leafletSection(page?.properties?.fields ?? [], t('LEAFLET.SECTION', { n: position + 1 })));
    const rule = leafletColours(theme).rule;
    if (!sections.length) return null;
    const numeralInk = theme?.secondary && theme?.accent && contrast(theme.secondary, theme.accent) >= 4.5 ? theme.secondary : theme?.primary;
    return (
        <section aria-labelledby="leaflet-contents" data-testid="leaflet-contents">
            <h2 id="leaflet-contents" className="text-[15px] font-semibold" style={{ color: theme?.primary }}>
                {t('WELCOME.CONTENTS')}
            </h2>
            <ol className="mt-2 border-t" style={{ borderColor: rule }}>
                {sections.map((section, position) => (
                    <li key={position} className="grid grid-cols-[var(--leaflet-margin,34px)_minmax(0,1fr)] items-baseline border-b py-2.5 text-base" style={{ borderColor: rule, color: theme?.primary }}>
                        <span className="tabular-nums" style={{ fontFamily: leafletSerif.style.fontFamily, fontWeight: 600, color: numeralInk }}>
                            {position + 1}
                        </span>
                        <span className="[overflow-wrap:anywhere]">
                            <ShortLabel short={section.shortTitle} full={section.title} />
                        </span>
                    </li>
                ))}
            </ol>
        </section>
    );
}
