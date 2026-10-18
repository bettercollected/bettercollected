import { CSSProperties } from 'react';

import { FormTheme, ThemeBackground, ThemePattern, ThemeStyle } from '@app/constants/theme';
import { leafletSerif } from '@app/assets/fonts/leaflet-serif';
import { cn } from '@app/shadcn/util/lib';
import { firstPartyImageUrl } from '@app/utils/first-party-image';
import ImageUrlField from '@app/views/molecules/theme/image-url-field';
import { formButtonStyle, themeRootProps } from '@app/views/molecules/theme/theme-root';

// Each editable colour, labelled by what it actually controls on the responder
// form (not by its internal role name), so the choice is legible to a creator.
export const THEME_ROLE_FIELDS: Array<{ key: 'accent' | 'primary' | 'secondary' | 'tertiary'; label: string }> = [
    { key: 'accent', label: 'Background' },
    { key: 'primary', label: 'Questions & text' },
    { key: 'secondary', label: 'Buttons' },
    { key: 'tertiary', label: 'Input borders' }
];

const PATTERNS: Array<{ key: ThemePattern; label: string }> = [
    { key: 'dots', label: 'Dots' },
    { key: 'grid', label: 'Grid' },
    { key: 'stripes', label: 'Stripes' }
];

/**
 * The one place the theme's background becomes CSS — used by the runtime page
 * ground, the mini previews and the editors alike, so what you preview is what
 * responders get. `accent` always stays underneath as the base colour (it's
 * what patterns draw on, what shows while an image loads, and the fallback for
 * incomplete gradient data).
 */
export function themeBackgroundStyle(theme?: Partial<FormTheme>): CSSProperties {
    const base: CSSProperties = { backgroundColor: theme?.accent };
    const bg = theme?.background;
    if (!bg || bg.type === 'color') return base;
    if (bg.type === 'gradient' && bg.gradientFrom && bg.gradientTo) {
        return { ...base, backgroundImage: `linear-gradient(${bg.gradientAngle ?? 135}deg, ${bg.gradientFrom}, ${bg.gradientTo})` };
    }
    if (bg.type === 'pattern' && bg.pattern) {
        // Decorative, deliberately faint: the pattern ink is the theme's
        // tertiary at ~15% alpha, so text contrast stays governed by accent.
        const ink = `${theme?.tertiary ?? '#818CA0'}26`;
        if (bg.pattern === 'dots') return { ...base, backgroundImage: `radial-gradient(${ink} 1.5px, transparent 1.5px)`, backgroundSize: '16px 16px' };
        if (bg.pattern === 'grid') return { ...base, backgroundImage: `linear-gradient(${ink} 1px, transparent 1px), linear-gradient(90deg, ${ink} 1px, transparent 1px)`, backgroundSize: '24px 24px' };
        return { ...base, backgroundImage: `repeating-linear-gradient(45deg, ${ink} 0px, ${ink} 1px, transparent 1px, transparent 12px)` };
    }
    if (bg.type === 'image' && bg.imageUrl) {
        return { ...base, backgroundImage: `url(${JSON.stringify(firstPartyImageUrl(bg.imageUrl))})`, backgroundSize: 'cover', backgroundPosition: 'center', backgroundRepeat: 'no-repeat' };
    }
    return base;
}

/**
 * An honest miniature of what the theme actually controls on the responder
 * form: question ink on the real ground (colour, gradient, pattern or image),
 * a bordered input, a button with white text. Real contrast, visible at a
 * glance — not four abstract boxes.
 */
export const ThemePreview = ({ color }: { color: FormTheme }) => {
    const { primary, secondary, tertiary } = color;
    const tokens = styleTokens(color.style);
    if (tokens.key === 'leaflet') {
        // The Leaflet miniature: section bar with its serif numeral, a
        // numbered question over a ruled option, and the button.
        const serif = { fontFamily: leafletSerif.style.fontFamily, fontWeight: 600 };
        const { rule } = leafletColours(color);
        return (
            <div style={themeBackgroundStyle(color)} className="flex flex-col items-stretch pb-3" data-testid="theme-preview-leaflet">
                <span className="flex items-baseline gap-2 px-4 py-1.5 text-white" style={{ background: secondary }}>
                    <span className="text-[14px] leading-none" style={serif}>
                        1
                    </span>
                    <span className="text-[12px] leading-tight" style={serif}>
                        Section
                    </span>
                </span>
                <span className="grid grid-cols-[20px_1fr] items-baseline px-4 pt-2 text-[12px] leading-tight font-semibold" style={{ color: primary }}>
                    <span className="text-[11px]" style={{ ...serif, color: contrast(secondary, color.accent) >= 4.5 ? secondary : primary }}>
                        1.1
                    </span>
                    Question
                </span>
                <span className="mx-4 ml-9 flex items-center gap-1.5 border-b py-1 text-[11px] leading-tight" style={{ borderColor: rule, color: primary }}>
                    <span className="h-2.5 w-2.5 rounded-full border-[1.5px] bg-white" style={{ borderColor: tertiary }} aria-hidden="true" />
                    Answer
                </span>
                <span style={{ background: secondary }} className="mt-2 ml-9 self-start rounded-[2px] px-2 py-0.5 text-[10px] leading-tight font-semibold text-white">
                    Continue
                </span>
            </div>
        );
    }
    // The theme's faces, corners, button style and highlight, as the form
    // wears them (theme-root.ts); nothing for a theme without them.
    const root = themeRootProps(color);
    return (
        <div {...root.attributes} style={{ ...themeBackgroundStyle(color), ...root.style, ...(color.bodyFont ? { fontFamily: 'var(--font-form)' } : {}) }} className="flex flex-col items-start gap-1.5 px-4 py-3">
            <span style={{ color: primary }} className={cn('form-title-face text-[13px] leading-tight', tokens.key === 'sheet' ? 'font-serif font-medium' : tokens.key === 'studio' ? 'font-bold tracking-tight' : 'font-semibold')}>
                Question
            </span>
            {/* Answer text wears primary on a white input, exactly like the
                runtime — so an illegible combination is visible right here. */}
            <span style={{ borderColor: '#E3E3E3', color: primary, borderRadius: tokens.fieldRadius }} className="w-full border bg-white px-2 py-1 text-[11px] leading-tight">
                Answer
            </span>
            <span style={formButtonStyle(secondary, tokens.inputRadius)} className="px-2 py-0.5 text-[10px] font-semibold leading-tight text-white">
                Continue
            </span>
        </div>
    );
};

export const Swatch = ({ color }: { color: string }) => <span className="border-black-300 h-3 w-3 rounded-full border" style={{ background: color }} aria-hidden="true" />;

// Relative luminance + contrast ratio (WCAG 2.1). Native <input type="color">
// always yields a 6-digit hex, so no short-hex handling is needed here.
function luminance(hex: string): number {
    const c = hex.replace('#', '');
    const channels = [0, 2, 4]
        .map((i) => parseInt(c.substring(i, i + 2), 16) / 255)
        .map((v) => (v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4)));
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2];
}

export function contrast(a: string, b: string): number {
    const l1 = luminance(a);
    const l2 = luminance(b);
    return (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);
}

/**
 * Live legibility read for a custom palette — the same roles the presets are
 * held to. Non-alarmist: it tells the creator what to fix, in plain terms.
 * A gradient is checked against both stops; an image can't be checked at all,
 * so it gets an honest advisory instead of false confidence.
 */
export const ContrastNotes = ({ theme }: { theme: FormTheme }) => {
    const notes: string[] = [];
    const bg = theme.background;
    const isGradient = bg?.type === 'gradient' && bg.gradientFrom && bg.gradientTo;
    const isImage = bg?.type === 'image' && bg.imageUrl;

    if (isGradient) {
        if (Math.min(contrast(theme.primary, bg!.gradientFrom!), contrast(theme.primary, bg!.gradientTo!)) < 4.5) notes.push('Question text may be hard to read on part of this gradient.');
        if (Math.min(contrast(theme.tertiary, bg!.gradientFrom!), contrast(theme.tertiary, bg!.gradientTo!)) < 3) notes.push('Input outlines may be hard to see on part of this gradient.');
    } else if (!isImage) {
        if (contrast(theme.primary, theme.accent) < 4.5) notes.push('Question text may be hard to read on this background.');
        if (contrast(theme.tertiary, theme.accent) < 3) notes.push('Input outlines may be hard to see on this background.');
    }
    // Inputs are always white at runtime and answers render in the primary
    // colour — a light primary is invisible there even if it reads fine on a
    // dark page (this is why there is no dark preset).
    if (contrast(theme.primary, '#FFFFFF') < 4.5) notes.push('Answer text may be hard to read inside the white input boxes.');
    if (contrast('#FFFFFF', theme.secondary) < 4.5) notes.push('White button text may be hard to read on this button colour.');
    if (isImage) notes.push('Contrast can’t be checked over an image — preview the form to confirm the text stays readable.');

    if (notes.length === 0) {
        return <p className="mt-1 text-[11px] font-medium text-success-700">Looks legible — contrast passes everywhere it matters.</p>;
    }
    return (
        <div className="mt-1 flex flex-col gap-1 rounded-md bg-brand-accent-100 px-2.5 py-2">
            {notes.map((note) => (
                <p key={note} className="text-[11px] leading-relaxed text-brand-olive">
                    {note}
                </p>
            ))}
        </div>
    );
};

/**
 * Appearance tokens per theme STYLE — how the form is dressed, resolved in one
 * place so the runtime, the previews and the editors always agree. Colours and
 * background stay orthogonal; a style only changes register (type, numerals,
 * edges, selection weight).
 *
 * - `ruledChoices`: options sit on 1px rules instead of in bordered boxes.
 * - `numbered`: pages become numbered sections and questions carry n.m
 *   numbers in a margin column (see utils/question-numbers.ts).
 * - `fieldRadius`/`cardRadius`: the corners fields and option cards draw:
 *   the theme's radius when it sets one (theme-root.ts), else the style's
 *   own `inputRadius`.
 */
export function styleTokens(style?: ThemeStyle) {
    switch (style) {
        case 'sheet':
            return {
                key: 'sheet' as const,
                labelClass: 'font-serif text-[17px] font-medium leading-snug lg:text-lg lg:leading-7',
                inputRadius: '4px',
                fieldRadius: 'var(--form-radius-field, 4px)',
                cardRadius: 'var(--form-radius-card, 4px)',
                divider: true, // ruled rows, like a printed questionnaire
                solidSelection: false,
                ruledChoices: false,
                numbered: false
            };
        case 'studio':
            return {
                key: 'studio' as const,
                labelClass: 'text-[19px] font-bold tracking-tight leading-snug lg:text-[21px]',
                inputRadius: '0px',
                fieldRadius: 'var(--form-radius-field, 0px)',
                cardRadius: 'var(--form-radius-card, 0px)',
                divider: false,
                solidSelection: true, // chosen options fill solid with white text
                ruledChoices: false,
                numbered: false
            };
        case 'leaflet':
            return {
                key: 'leaflet' as const,
                labelClass: 'text-[18px] font-semibold leading-[1.4]',
                inputRadius: '4px',
                fieldRadius: 'var(--form-radius-field, 4px)',
                cardRadius: 'var(--form-radius-card, 4px)',
                divider: false,
                solidSelection: false,
                ruledChoices: true, // options on 1px rules, standard controls
                numbered: true // numbered section bars, n.m questions in a margin column
            };
        default:
            return {
                key: 'classic' as const,
                labelClass: 'text-base font-semibold leading-snug lg:text-lg lg:leading-7',
                inputRadius: '6px',
                fieldRadius: 'var(--form-radius-field, 6px)',
                cardRadius: 'var(--form-radius-card, 6px)',
                divider: false,
                solidSelection: false,
                ruledChoices: false,
                numbered: false
            };
    }
}

/** `#rrggbb` mixed with another `#rrggbb`: `weight` of `a`, the rest `b`. */
export function mixHex(a: string, b: string, weight: number): string {
    const parse = (hex: string) => [0, 2, 4].map((i) => parseInt(hex.replace('#', '').substring(i, i + 2), 16));
    const [ca, cb] = [parse(a), parse(b)];
    return (
        '#' +
        ca
            .map((value, i) => Math.round(value * weight + cb[i] * (1 - weight)))
            .map((value) => value.toString(16).padStart(2, '0'))
            .join('')
            .toUpperCase()
    );
}

const isHex = (value?: string): value is string => !!value && /^#[0-9a-fA-F]{6}$/.test(value);

/**
 * Secondary text (descriptions, hints) in the theme's own ink, a step lighter
 * than the questions: the ink mixed a little towards the page, kept at 7:1 or
 * more on it (else the ink itself). A fixed grey would sit off-hue on the
 * tinted presets.
 */
export function softInk(theme?: Partial<FormTheme>): string {
    const primary = isHex(theme?.primary) ? theme!.primary : '#101828';
    if (!isHex(theme?.accent)) return primary;
    const candidate = mixHex(primary, theme!.accent, 0.82);
    return contrast(candidate, theme!.accent) >= 7 ? candidate : primary;
}

/**
 * The theme's action colour used as text (links, numerals, the page count):
 * the secondary where it reads at 4.5:1 on the page, else the ink.
 */
export function actionInk(theme?: Partial<FormTheme>): string {
    const primary = isHex(theme?.primary) ? theme!.primary : '#101828';
    if (!isHex(theme?.secondary) || !isHex(theme?.accent)) return primary;
    return contrast(theme!.secondary, theme!.accent) >= 4.5 ? theme!.secondary : primary;
}

/**
 * The edge of a field that needs an answer: signal red where it reaches the
 * 3:1 a control boundary needs on the page, else the ink.
 */
export function invalidEdge(theme?: Partial<FormTheme>): string {
    const accent = isHex(theme?.accent) ? theme!.accent : '#FFFFFF';
    return contrast(LEAFLET_SIGNAL_RED, accent) >= 3 ? LEAFLET_SIGNAL_RED : theme?.primary || '#101828';
}

/** Danger red for required markers (DESIGN.md §1). */
export const REQUIRED_RED = '#C43D3D';

/**
 * The colour of the required marker: danger red where it reaches 4.5:1 on the
 * form's ground, the theme's ink where it doesn't (the red falls to about
 * 4.2:1 on the tinted presets).
 */
export function requiredMarkColour(theme?: Partial<FormTheme>): string {
    if (theme?.style === 'leaflet') return leafletColours(theme).required;
    const accent = isHex(theme?.accent) ? theme!.accent : '#FFFFFF';
    return contrast(REQUIRED_RED, accent) >= 4.5 ? REQUIRED_RED : theme?.primary || '#101828';
}

/** Signal red for required markers in the Leaflet style. */
export const LEAFLET_SIGNAL_RED = '#C8102E';

/**
 * The colours the Leaflet style derives from a theme's four roles, each held
 * to the same contrast rules as the roles themselves:
 *
 * - `band`: the pale intro band, a tint of the secondary over the page, kept
 *   light enough that the theme's ink reads at 7:1 or more on it;
 * - `rule`: the 1px rules between options and under the header (separators,
 *   not control edges: the radio and checkbox controls carry the tertiary at
 *   full strength);
 * - `required`: signal red where it reaches 4.5:1 on the page, else the ink.
 */
export function leafletColours(theme?: Partial<FormTheme>) {
    const accent = isHex(theme?.accent) ? theme!.accent : '#FFFFFF';
    const primary = isHex(theme?.primary) ? theme!.primary : '#101828';
    const secondary = isHex(theme?.secondary) ? theme!.secondary : '#1649E2';
    const tertiary = isHex(theme?.tertiary) ? theme!.tertiary : '#818CA0';
    let band = accent;
    for (const weight of [0.09, 0.07, 0.05, 0.03]) {
        const candidate = mixHex(secondary, accent, weight);
        if (contrast(primary, candidate) >= 7) {
            band = candidate;
            break;
        }
    }
    return {
        band,
        rule: mixHex(tertiary, accent, 0.4),
        required: contrast(LEAFLET_SIGNAL_RED, accent) >= 4.5 ? LEAFLET_SIGNAL_RED : primary
    };
}

const STYLE_OPTIONS: Array<{ key: ThemeStyle; label: string; hint: string }> = [
    { key: 'classic', label: 'Classic', hint: 'Clean and quiet — the default.' },
    { key: 'sheet', label: 'Sheet', hint: 'Like a printed document: serif questions, ruled rows.' },
    { key: 'studio', label: 'Studio', hint: 'Bold and graphic: heavy type, square edges.' },
    { key: 'leaflet', label: 'Leaflet', hint: 'Like a clear information leaflet: numbered sections, margin notes.' }
];

/** Shared style picker for the theme editors (builder Design tab, Themes page). */
export const ThemeStyleEditor = ({ value, onChange }: { value?: ThemeStyle; onChange: (style: ThemeStyle) => void }) => {
    const current = value ?? 'classic';
    return (
        <div className="flex flex-col gap-2">
            <span className="text-black-700 text-xs">Style</span>
            <div className="border-black-300 flex overflow-hidden rounded-md border" role="group" aria-label="Form style">
                {STYLE_OPTIONS.map((option) => (
                    <button
                        key={option.key}
                        type="button"
                        aria-pressed={current === option.key}
                        title={option.hint}
                        onClick={() => onChange(option.key)}
                        className={cn('flex-1 px-2 py-1.5 text-[11px] font-medium transition-colors', current === option.key ? 'bg-brand-100 text-brand-600' : 'text-black-600 hover:bg-black-100 bg-white')}
                    >
                        {option.label}
                    </button>
                ))}
            </div>
            <p className="text-black-600 text-[11px] leading-relaxed">{STYLE_OPTIONS.find((o) => o.key === current)?.hint}</p>
        </div>
    );
};

const BACKGROUND_TYPES: Array<{ key: ThemeBackground['type']; label: string }> = [
    { key: 'color', label: 'Colour' },
    { key: 'gradient', label: 'Gradient' },
    { key: 'pattern', label: 'Pattern' },
    { key: 'image', label: 'Image' }
];

/**
 * Shared background controls for the theme editors (builder Design tab and the
 * Themes page). Emits a full ThemeBackground (or undefined for plain colour,
 * keeping legacy themes byte-identical).
 */
export const ThemeBackgroundEditor = ({ theme, onChange }: { theme: FormTheme; onChange: (background?: ThemeBackground) => void }) => {
    const bg = theme.background;
    const type = bg?.type ?? 'color';

    const setType = (nextType: ThemeBackground['type']) => {
        if (nextType === 'color') {
            onChange(undefined);
            return;
        }
        if (nextType === 'gradient') {
            onChange({ type: 'gradient', gradientFrom: bg?.gradientFrom ?? theme.accent, gradientTo: bg?.gradientTo ?? theme.secondary, gradientAngle: bg?.gradientAngle ?? 135 });
            return;
        }
        if (nextType === 'pattern') {
            onChange({ type: 'pattern', pattern: bg?.pattern ?? 'dots' });
            return;
        }
        onChange({ type: 'image', imageUrl: bg?.imageUrl ?? '' });
    };

    return (
        <div className="flex flex-col gap-2.5">
            <span className="text-black-700 text-xs">Page background</span>
            <div className="border-black-300 flex overflow-hidden rounded-md border" role="group" aria-label="Background type">
                {BACKGROUND_TYPES.map((option) => (
                    <button
                        key={option.key}
                        type="button"
                        aria-pressed={type === option.key}
                        onClick={() => setType(option.key)}
                        className={cn('flex-1 px-2 py-1.5 text-[11px] font-medium transition-colors', type === option.key ? 'bg-brand-100 text-brand-600' : 'text-black-600 hover:bg-black-100 bg-white')}
                    >
                        {option.label}
                    </button>
                ))}
            </div>

            {type === 'color' && <p className="text-black-600 text-[11px] leading-relaxed">Uses the background colour above.</p>}

            {type === 'gradient' && bg?.type === 'gradient' && (
                <div className="flex flex-col gap-2">
                    {(
                        [
                            { key: 'gradientFrom', label: 'From' },
                            { key: 'gradientTo', label: 'To' }
                        ] as const
                    ).map((stop) => (
                        <div key={stop.key} className="flex items-center justify-between gap-3">
                            <span className="text-black-700 text-xs">{stop.label}</span>
                            <span className="flex items-center gap-2">
                                <span className="text-black-600 text-[11px] uppercase tabular-nums">{bg[stop.key]}</span>
                                <input type="color" aria-label={`Gradient ${stop.label.toLowerCase()} colour`} value={bg[stop.key]} onChange={(e) => onChange({ ...bg, [stop.key]: e.target.value })} className="border-black-300 h-7 w-9 cursor-pointer rounded border bg-white p-0.5" />
                            </span>
                        </div>
                    ))}
                    <div className="flex items-center justify-between gap-3">
                        <span className="text-black-700 text-xs">Angle</span>
                        <span className="flex items-center gap-2">
                            <input type="range" min={0} max={360} step={45} aria-label="Gradient angle" value={bg.gradientAngle ?? 135} onChange={(e) => onChange({ ...bg, gradientAngle: Number(e.target.value) })} className="w-24 accent-[#123FC9]" />
                            <span className="text-black-600 w-8 text-right text-[11px] tabular-nums">{bg.gradientAngle ?? 135}°</span>
                        </span>
                    </div>
                </div>
            )}

            {type === 'pattern' && bg?.type === 'pattern' && (
                <div className="flex gap-2" role="group" aria-label="Pattern">
                    {PATTERNS.map((pattern) => (
                        <button
                            key={pattern.key}
                            type="button"
                            aria-pressed={bg.pattern === pattern.key}
                            onClick={() => onChange({ ...bg, pattern: pattern.key })}
                            className={cn('flex-1 overflow-hidden rounded-md border text-center', bg.pattern === pattern.key ? 'border-brand-500 ring-1 ring-brand-500' : 'border-black-300 hover:border-black-400')}
                        >
                            <span className="block h-8 w-full" style={themeBackgroundStyle({ ...theme, background: { type: 'pattern', pattern: pattern.key } })} aria-hidden="true" />
                            <span className="text-black-700 block bg-white py-1 text-[10px] font-medium">{pattern.label}</span>
                        </button>
                    ))}
                </div>
            )}

            {type === 'image' && bg?.type === 'image' && (
                <ImageUrlField value={bg.imageUrl ?? ''} onChange={(imageUrl) => onChange({ ...bg, imageUrl })} />
            )}
        </div>
    );
};
