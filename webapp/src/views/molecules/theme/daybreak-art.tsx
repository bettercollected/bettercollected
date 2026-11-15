import { CSSProperties } from 'react';

import { FormTheme, isHexColour } from '@app/constants/theme';
import { contrast } from '@app/utils/color-contrast';

/**
 * The Daybreak scene (`background.artwork: 'daybreak'`), drawn here and nowhere
 * else: flat shapes in first-party inline SVG, no image, no request, no
 * third-party asset. Two places:
 *
 * - a sun in the corner of every page, painted as the page's background image
 *   (`daybreakCornerStyle`, used by themeBackgroundStyle), so it sits under the
 *   questions, never over them, and does not scroll;
 * - on the ending, a flat sun that rises behind two hills over one second
 *   (ease-out), then a check draws itself inside it (`DaybreakSunrise`). It
 *   plays once, when the ending appears; under `prefers-reduced-motion` the
 *   finished picture is there at once. No confetti, no sound.
 *
 * Both are decorative (`aria-hidden`): the ending's words say everything.
 */

/** The sun, a pale sun for the corner's large disc, and the rule's deep sun. */
export const DAYBREAK_SUN = '#FFB400';
export const DAYBREAK_SUN_TINT = '#FFF1C7';
/** The "Why we ask this" rule: the sun deepened until it reads at 3:1 on the page (3.6:1 on #F3F6FF). */
export const DAYBREAK_RULE = '#B07400';

/** Does the theme wear the Daybreak scene? */
export const hasDaybreakScene = (theme?: Partial<FormTheme> | null) => theme?.background?.artwork === 'daybreak';

/**
 * The colour of the "why we ask" rule on a Daybreak page: the deep sun where it
 * reads at 3:1 on the page, else the ink (the same clamp as a highlight's rule,
 * theme-root.ts `highlightColours`).
 */
export function daybreakRule(theme?: Partial<FormTheme> | null): string {
    const page = isHexColour(theme?.accent) ? theme!.accent! : '#FFFFFF';
    const ink = isHexColour(theme?.primary) ? theme!.primary! : '#101828';
    return contrast(DAYBREAK_RULE, page) >= 3 ? DAYBREAK_RULE : ink;
}

// Two quarter discs centred on the page's top right corner: a pale one and the
// sun inside it. 260 units square; drawn at 130 to 260px (see below).
const CORNER_SVG = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 260 260"><path d="M260 0H0A260 260 0 0 0 260 260Z" fill="${DAYBREAK_SUN_TINT}"/><path d="M260 0H164A96 96 0 0 0 260 96Z" fill="${DAYBREAK_SUN}"/></svg>`;

/** The page ground's addition for the corner sun: an image at the top right, scaled with the page. */
export function daybreakCornerStyle(compact = false): CSSProperties {
    return {
        backgroundImage: `url("data:image/svg+xml,${encodeURIComponent(CORNER_SVG)}")`,
        backgroundRepeat: 'no-repeat',
        backgroundPosition: 'top right',
        backgroundSize: compact ? '48px auto' : 'clamp(130px, 18vw, 260px) auto'
    };
}

/** `weight` of `a` over the rest `b`, as #RRGGBB. */
function mix(a: string, b: string, weight: number): string {
    const channel = (hex: string, i: number) => parseInt(hex.slice(1 + i * 2, 3 + i * 2), 16);
    return '#' + [0, 1, 2].map((i) => Math.round(channel(a, i) * weight + channel(b, i) * (1 - weight)).toString(16).padStart(2, '0')).join('').toUpperCase();
}

// The ending's one authored moment. Ease-out-expo; transform and stroke only.
const SUNRISE_CSS = `
.bc-daybreak-rise{animation:bc-daybreak-rise 1000ms cubic-bezier(.16,1,.3,1) both}
.bc-daybreak-check{stroke-dasharray:60;animation:bc-daybreak-draw 520ms cubic-bezier(.16,1,.3,1) 520ms both}
@keyframes bc-daybreak-rise{from{transform:translateY(74px)}to{transform:none}}
@keyframes bc-daybreak-draw{from{stroke-dashoffset:60}to{stroke-dashoffset:0}}
@media (prefers-reduced-motion:reduce){.bc-daybreak-rise,.bc-daybreak-check{animation:none}.bc-daybreak-check{stroke-dasharray:none}}
`;

/**
 * The band along the top of the ending: the sky (the action colour at a tenth
 * over the page), two hills in the action colour, the sun rising behind them
 * and the check inside it in the questions' ink, and one small coral spark.
 * Ink on the sun reads at 9.9:1.
 */
export function DaybreakSunrise({ theme }: { theme?: Partial<FormTheme> | null }) {
    const action = isHexColour(theme?.secondary) ? theme!.secondary! : '#1649E2';
    const page = isHexColour(theme?.accent) ? theme!.accent! : '#F3F6FF';
    const ink = isHexColour(theme?.primary) ? theme!.primary! : '#0E1737';
    return (
        <div className="relative h-[130px] w-full shrink-0 overflow-hidden sm:h-[184px]" style={{ background: mix(action, page, 0.1) }} data-testid="daybreak-sunrise" aria-hidden="true">
            <style>{SUNRISE_CSS}</style>
            <svg className="absolute inset-0 h-full w-full" viewBox="0 0 1200 184" preserveAspectRatio="xMaxYMax slice" focusable="false">
                <g className="bc-daybreak-rise">
                    <circle cx="864" cy="103" r="74" fill={DAYBREAK_SUN} opacity=".34" />
                    <circle cx="864" cy="103" r="55" fill={DAYBREAK_SUN} />
                    <path className="bc-daybreak-check" d="M849 105l9 10 22 -24" stroke={ink} strokeWidth="7" fill="none" strokeLinecap="round" strokeLinejoin="round" />
                </g>
                <path d="M0 184 V143 C144 92 312 95 480 136 S744 174 936 128 S1104 114 1224 110 V184 Z" fill={action} opacity=".17" />
                <path d="M0 184 V165 C240 132 552 154 792 176 S1080 187 1200 154 V184 Z" fill={action} opacity=".30" />
                <circle cx="156" cy="40" r="6" fill="#FF6A48" />
            </svg>
        </div>
    );
}
