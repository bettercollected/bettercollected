import { CSSProperties } from 'react';

import marblePanel960Avif from '@app/assets/themes/marble/marble-panel-960x1200.avif';
import marblePanel960Webp from '@app/assets/themes/marble/marble-panel-960x1200.webp';
import marblePanel1440Avif from '@app/assets/themes/marble/marble-panel-1440x1800.avif';
import marblePanel1440Webp from '@app/assets/themes/marble/marble-panel-1440x1800.webp';
import marbleStripAvif from '@app/assets/themes/marble/marble-strip-1560x240.avif';
import marbleStripWebp from '@app/assets/themes/marble/marble-strip-1560x240.webp';
import marblePlaceholders from '@app/assets/themes/marble/placeholders.json';
import { FormTheme, THEME_ARTWORKS, ThemeArtwork, isHexColour } from '@app/constants/theme';
import { FormSlideLayout } from '@app/models/enums/form';
import { cn } from '@app/shadcn/util/lib';
import { contrast } from '@app/utils/color-contrast';

/**
 * Built-in theme artwork (`background.artwork`): first-party images bundled
 * with the app (assets/themes/, made by scripts/marble), so a respondent's
 * browser fetches them from the form's own origin and from nobody else.
 * AVIF with a WebP fallback, a blurred placeholder inlined as a data URI
 * while they load, and always decorative (`alt=""`): no text sits on them.
 */

/** A bundled image's address (Next gives an object with `src`; other bundlers the string). */
const assetUrl = (asset: { src: string } | string) => (typeof asset === 'string' ? asset : asset.src);

const MARBLE = {
    panelAvif: `${assetUrl(marblePanel960Avif)} 960w, ${assetUrl(marblePanel1440Avif)} 1440w`,
    panelWebp: `${assetUrl(marblePanel960Webp)} 960w, ${assetUrl(marblePanel1440Webp)} 1440w`,
    panelFallback: assetUrl(marblePanel960Webp),
    stripAvif: assetUrl(marbleStripAvif),
    stripWebp: assetUrl(marbleStripWebp)
};

/** The theme's artwork, if it names one the app has. */
export function themeArtwork(theme?: Partial<FormTheme> | null): ThemeArtwork | null {
    const artwork = theme?.background?.artwork;
    return artwork && (THEME_ARTWORKS as readonly string[]).includes(artwork) ? artwork : null;
}

/** The layouts with a picture half beside the text. */
export function isBesideLayout(layout?: FormSlideLayout | string | null) {
    return layout === FormSlideLayout.TWO_COLUMN_IMAGE_LEFT || layout === FormSlideLayout.TWO_COLUMN_IMAGE_RIGHT;
}

/** The layouts that show a picture (beside the text or behind it). */
export function hasPictureSlot(layout?: FormSlideLayout | string | null) {
    return isBesideLayout(layout) || layout === FormSlideLayout.SINGLE_COLUMN_IMAGE_BACKGROUND;
}

/**
 * The colours of the striped headband at the artwork's spine: the
 * highlight (else the secondary) and the page colour. Decorative.
 */
function headbandStyle(theme: Partial<FormTheme> | null | undefined, direction: 'to bottom' | 'to right'): CSSProperties {
    const a = isHexColour(theme?.highlight) ? theme!.highlight! : (theme?.secondary ?? '#1E4D3B');
    const b = isHexColour(theme?.accent) ? theme!.accent! : '#FFFFFF';
    return { backgroundImage: `repeating-linear-gradient(${direction}, ${a} 0 6px, ${b} 6px 10px)` };
}

/**
 * The artwork filling a picture half: the tall panel from `lg` up (or
 * always, in a desktop preview), the strip as a band above the text on
 * phones, with the headband along the edge that meets the text.
 */
export function ThemeArtworkPanel({ theme, layout, desktop = false }: { theme?: Partial<FormTheme> | null; layout?: FormSlideLayout | null; /** Always the desktop panel (the builder canvas). */ desktop?: boolean }) {
    if (themeArtwork(theme) !== 'marble') return null;
    // The spine: the edge of the picture half that meets the text.
    const spineLeft = layout !== FormSlideLayout.TWO_COLUMN_IMAGE_LEFT;
    const lg = desktop ? '' : 'lg:';
    return (
        <div className="absolute inset-0 overflow-hidden" style={{ backgroundImage: `url(${marblePlaceholders.panel})`, backgroundSize: 'cover', backgroundPosition: 'center' }} data-testid="theme-artwork" aria-hidden="true">
            <picture>
                {/* The panel: from 1024px wide (the two-column layout), or always on the canvas. */}
                <source media={desktop ? undefined : '(min-width: 1024px)'} type="image/avif" srcSet={MARBLE.panelAvif} sizes="50vw" />
                <source media={desktop ? undefined : '(min-width: 1024px)'} type="image/webp" srcSet={MARBLE.panelWebp} sizes="50vw" />
                {!desktop && <source type="image/avif" srcSet={MARBLE.stripAvif} />}
                <img src={desktop ? MARBLE.panelFallback : MARBLE.stripWebp} alt="" decoding="async" className="h-full w-full object-cover" />
            </picture>
            {/* The headband: along the bottom on phones, along the spine beside the text from lg up. */}
            <span className={cn('absolute inset-y-0 w-3', !desktop && 'hidden lg:block', spineLeft ? `${lg}left-0` : `${lg}right-0`)} style={headbandStyle(theme, 'to bottom')} />
            {!desktop && <span className="absolute inset-x-0 bottom-0 h-2 lg:hidden" style={headbandStyle(theme, 'to right')} />}
        </div>
    );
}

/**
 * The artwork as a band along the top of a page (the ending when its layout
 * has no picture half): the strip, with the headband under it.
 */
export function ThemeArtworkBand({ theme }: { theme?: Partial<FormTheme> | null }) {
    if (themeArtwork(theme) !== 'marble') return null;
    return (
        <div className="relative h-20 w-full shrink-0 overflow-hidden sm:h-[120px]" style={{ backgroundImage: `url(${marblePlaceholders.strip})`, backgroundSize: 'cover', backgroundPosition: 'center' }} data-testid="theme-artwork-band" aria-hidden="true">
            <picture>
                <source type="image/avif" srcSet={MARBLE.stripAvif} />
                <img src={MARBLE.stripWebp} alt="" decoding="async" className="h-full w-full object-cover" />
            </picture>
            <span className="absolute inset-x-0 bottom-0 h-2" style={headbandStyle(theme, 'to right')} />
        </div>
    );
}

export interface GreetingCover {
    /** The theme the cover's text half wears: the button colour as its ground, the page colour as its ink. */
    theme: FormTheme;
    /** Variables for the cover's root: its buttons in the page colour with the button colour as their text. */
    style: CSSProperties;
}

/**
 * The cover: a welcome page set beside the theme's artwork (an image layout,
 * no image of its own) sets its text half like a clothbound cover, in the
 * button colour with the page colour as the ink, and its button the other
 * way round. Only where the two read at 4.5:1 on each other, and not for
 * the Leaflet style or a private form (whose sign-in notes keep the app's
 * own colours); null otherwise, and the page renders as before.
 */
export function greetingCover(theme: FormTheme | null | undefined, layout?: FormSlideLayout | null, imageUrl?: string | null, { privateForm = false }: { privateForm?: boolean } = {}): GreetingCover | null {
    if (!theme || !themeArtwork(theme) || !isBesideLayout(layout) || imageUrl?.trim() || privateForm || theme.style === 'leaflet') return null;
    if (!isHexColour(theme.secondary) || !isHexColour(theme.accent) || contrast(theme.accent, theme.secondary) < 4.5) return null;
    const cloth = theme.secondary;
    const paper = theme.accent;
    const cover: FormTheme = { ...theme, accent: cloth, primary: paper, secondary: paper, tertiary: paper, highlight: null, selection: null, background: undefined };
    // An outlined button already reads on the cover (theme-root.ts takes the
    // cover's own colours); a filled or pill one turns to the page colour.
    const style: Record<string, string> = theme.buttonStyle === 'outlined' ? {} : { '--form-button-bg': paper, '--form-button-fg': cloth, '--form-button-edge': 'none' };
    return { theme: cover, style: style as CSSProperties };
}
