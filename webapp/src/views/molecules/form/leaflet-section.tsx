import { ReactNode } from 'react';

import { leafletSerif } from '@app/assets/fonts/leaflet-serif';
import { FormTheme } from '@app/constants/theme';
import useRespondentLanguage from '@app/lib/hooks/use-respondent-language';
import { StandardFormFieldDto } from '@app/models/dtos/form';
import { FormSlideLayout } from '@app/models/enums/form';
import { cn } from '@app/shadcn/util/lib';
import { leafletSection } from '@app/utils/leaflet-sections';
import { contrast, leafletColours, softInk } from '@app/views/molecules/theme/theme-shared';
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
export function LeafletSectionBar({ theme, numeral, title, layout, headingLevel = 2, className }: { theme?: Partial<FormTheme>; numeral?: number | string; title: ReactNode; layout?: FormSlideLayout | null; headingLevel?: 1 | 2; className?: string }) {
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
                    <Heading className={cn('grid grid-cols-[34px_minmax(0,1fr)] items-baseline', hang && '@min-[880px]/page:block')} style={serif}>
                        <span
                            className={cn('text-[28px] leading-none tabular-nums', hang && '@min-[880px]/page:absolute @min-[880px]/page:top-0 @min-[880px]/page:-left-16 @min-[880px]/page:w-12 @min-[880px]/page:text-right')}
                            data-testid="leaflet-section-numeral"
                        >
                            {numeral}
                        </span>
                        <span className="text-[22px] leading-[1.25] text-balance [overflow-wrap:anywhere]">{title}</span>
                    </Heading>
                )}
            </div>
        </div>
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
 * The cover's contents: every page's section number and title. A page without
 * its own opening heading is listed under the same title its section bar
 * shows (the form's title), so the list matches the pages. Only when no page
 * has a heading of its own would the list just repeat the cover's title, so
 * it states how many pages the form has instead.
 */
export function LeafletContents({ pages, theme, formTitle }: { pages: ReadonlyArray<StandardFormFieldDto> | undefined; theme?: Partial<FormTheme>; formTitle: string }) {
    const { t } = useRespondentLanguage();
    const sections = (pages ?? []).map((page) => leafletSection(page?.properties?.fields ?? [], formTitle));
    const rule = leafletColours(theme).rule;
    if (!sections.some((section) => section.titleFromPage)) {
        return (
            <p className="text-base" style={{ color: softInk(theme) }}>
                {t('WELCOME.PAGE_COUNT', { count: sections.length })}
            </p>
        );
    }
    const numeralInk = theme?.secondary && theme?.accent && contrast(theme.secondary, theme.accent) >= 4.5 ? theme.secondary : theme?.primary;
    return (
        <section aria-labelledby="leaflet-contents" data-testid="leaflet-contents">
            <h2 id="leaflet-contents" className="text-[15px] font-semibold" style={{ color: theme?.primary }}>
                {t('WELCOME.CONTENTS')}
            </h2>
            <ol className="mt-2 border-t" style={{ borderColor: rule }}>
                {sections.map((section, position) => (
                    <li key={position} className="grid grid-cols-[34px_minmax(0,1fr)] items-baseline border-b py-2.5 text-base" style={{ borderColor: rule, color: theme?.primary }}>
                        <span className="tabular-nums" style={{ fontFamily: leafletSerif.style.fontFamily, fontWeight: 600, color: numeralInk }}>
                            {position + 1}
                        </span>
                        <span className="[overflow-wrap:anywhere]">{section.title}</span>
                    </li>
                ))}
            </ol>
        </section>
    );
}
