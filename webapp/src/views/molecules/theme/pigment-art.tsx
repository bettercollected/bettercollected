import { CSSProperties } from 'react';

import { FormTheme, PIGMENT_BAND, PIGMENT_BAND_FALLBACK_INK, isHexColour } from '@app/constants/theme';
import { contrast } from '@app/utils/color-contrast';
import { hasDaybreakScene } from '@app/views/molecules/theme/daybreak-art';

/**
 * The Pigment scene (`background.artwork: 'pigment'`), drawn here and nowhere else:
 * flat shapes in first-party inline SVG and CSS, no image, no request, no
 * third-party asset, and none of the app's colour variables (a respondent page
 * never reads them). Two places:
 *
 * - a sun-yellow band over the questions: the header bar's ground
 *   (`pigmentBandStyle`, used by the question page's header), with the form's
 *   ink on it (11.3:1; `pigmentBandInk` keeps every piece of text and every icon
 *   drawn on the band at 4.5:1 for any theme) and the progress line in the action colour;
 * - on the ending, an iris disc that holds the check, and five flat shapes
 *   (circle, square, triangle, half-circle, ring) that pop in around it once,
 *   staggered over about 0.7 s, then rest (`PigmentShapes`). Under
 *   `prefers-reduced-motion` they are simply there, placed. No sound, no confetti.
 *
 * Both are decorative (`aria-hidden`): the ending's words say everything.
 */

/** The band's sun-yellow, and the five pigments of the shapes (the same flat fills as the choice keys). */
export const PIGMENT_SUN = PIGMENT_BAND;
export const PIGMENT_TOMATO = '#FF8A73';
export const PIGMENT_SKY = '#6BBEF7';
export const PIGMENT_MINT = '#5FD9B0';
export const PIGMENT_ORCHID = '#D9A0FF';
/** The "Why we ask this" rule: the tomato deepened until it reads at 3:1 on the cream page (4.1:1). */
export const PIGMENT_RULE = '#D44A33';
/** Does the theme wear the Pigment scene? */
export const hasPigmentScene = (theme?: Partial<FormTheme> | null) => theme?.background?.artwork === 'pigment';

/** Does the theme wear a scene that draws the ending's picture and puts its message right under it (Daybreak or Pigment)? */
export const hasEndingScene = (theme?: Partial<FormTheme> | null) => hasDaybreakScene(theme) || hasPigmentScene(theme);

/**
 * The colour of the "why we ask" rule on a Pigment page: the deep tomato where it
 * reads at 3:1 on the page, else the ink (the same clamp as a highlight's rule,
 * theme-root.ts `highlightColours`).
 */
export function pigmentRule(theme?: Partial<FormTheme> | null): string {
    const page = isHexColour(theme?.accent) ? theme!.accent! : '#FFFFFF';
    const ink = isHexColour(theme?.primary) ? theme!.primary! : '#101828';
    return contrast(PIGMENT_RULE, page) >= 3 ? PIGMENT_RULE : ink;
}

/**
 * The ink of every piece of text and every icon drawn on the sun-yellow band (the
 * page count, the Back control and its chevron): the theme's `primary` where it
 * reads at 4.5:1 on the band (the preset's #1A1238 does, 11.3:1), else the preset's
 * dark ink. The same clamp as `choiceKeyColours` and `pigmentRule`: a custom theme
 * that keeps the artwork, or `update_theme`, cannot leave grey text on the yellow.
 * The contrast guard measures `primary` on the band too (key `band`), so a creator
 * is told; this keeps a form that already stores such a theme readable.
 */
export function pigmentBandInk(theme?: Partial<FormTheme> | null): string {
    const primary = theme?.primary;
    return isHexColour(primary) && contrast(primary!, PIGMENT_BAND) >= 4.5 ? primary! : PIGMENT_BAND_FALLBACK_INK;
}

/** The header bar's ground on a Pigment question page: the sun-yellow band, as the comp draws it. */
export function pigmentBandStyle(): CSSProperties {
    return { background: PIGMENT_SUN };
}

/** The picker's thumbnail ground: a thin sun-yellow band along the top. */
export function pigmentThumbnailStyle(): CSSProperties {
    return { backgroundImage: `linear-gradient(${PIGMENT_SUN} 0 14px, transparent 14px)`, backgroundRepeat: 'no-repeat' };
}

// The ending's one authored moment: each shape pops from nothing to its size
// with a little overshoot, once, staggered (0, 80, 160, 240, 340 ms, 360 ms
// each: done at 0.7 s). Transform only. A shape is placed before and after.
const SHAPES_CSS = `
.bc-pigment-pop{transform-box:fill-box;transform-origin:center;animation:bc-pigment-pop 360ms cubic-bezier(.34,1.56,.64,1) both}
.bc-pigment-pop[data-n="1"]{animation-delay:0ms}
.bc-pigment-pop[data-n="2"]{animation-delay:80ms}
.bc-pigment-pop[data-n="3"]{animation-delay:160ms}
.bc-pigment-pop[data-n="4"]{animation-delay:240ms}
.bc-pigment-pop[data-n="5"]{animation-delay:340ms}
@keyframes bc-pigment-pop{from{transform:scale(0)}to{transform:none}}
@media (prefers-reduced-motion:reduce){.bc-pigment-pop{animation:none}}
`;

/**
 * The band along the top of the ending: sun-yellow, with an iris disc that holds
 * the check in white, and five flat shapes placed around it. The picture is one
 * square-ish composition (a 320 by 160 box, drawn at 320 by 160 from `sm` and
 * at 256 by 128 on a phone) centred in a band that is 150px tall on a phone and
 * 200px from `sm`: 20px and 11px of yellow above and below it, and every shape
 * at least 8 units inside the box, so nothing touches an edge or is cropped.
 * White on the iris reads at 7.4:1; the shapes carry no text.
 */
export function PigmentShapes({ theme }: { theme?: Partial<FormTheme> | null }) {
    const action = isHexColour(theme?.secondary) ? theme!.secondary! : '#4B35DB';
    // the ring is drawn on the yellow band: the ink that reads there (pigmentBandInk)
    const ink = pigmentBandInk(theme);
    return (
        <div className="relative flex h-[150px] w-full shrink-0 items-center justify-center overflow-hidden sm:h-[200px]" style={{ background: PIGMENT_SUN }} data-testid="pigment-shapes" aria-hidden="true">
            <style>{SHAPES_CSS}</style>
            <svg className="h-[128px] w-[256px] sm:h-[160px] sm:w-[320px]" viewBox="0 0 320 160" focusable="false" data-testid="pigment-picture">
                <circle cx="160" cy="80" r="46" fill={action} />
                <path d="M139 82l15 16 30 -34" stroke="#FFFFFF" strokeWidth="9" fill="none" strokeLinecap="round" strokeLinejoin="round" />
                <circle className="bc-pigment-pop" data-n="1" data-shape="circle" cx="76" cy="50" r="16" fill={PIGMENT_TOMATO} />
                <rect className="bc-pigment-pop" data-n="2" data-shape="square" x="226" y="26" width="30" height="30" fill={PIGMENT_SKY} />
                <path className="bc-pigment-pop" data-n="3" data-shape="triangle" d="M236 134H268L252 104Z" fill={PIGMENT_MINT} />
                <path className="bc-pigment-pop" data-n="4" data-shape="half-circle" d="M50 132a26 26 0 0 1 52 0Z" fill={PIGMENT_ORCHID} />
                <circle className="bc-pigment-pop" data-n="5" data-shape="ring" cx="286" cy="86" r="11" fill="none" stroke={ink} strokeWidth="6" />
            </svg>
        </div>
    );
}
