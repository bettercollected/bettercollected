import { CSSProperties } from 'react';

import { FormTheme, ThemeArtwork, ThemeBackground, ThemePattern, ThemeStyle, isHexColour } from '@app/constants/theme';
import { leafletSerif } from '@app/assets/fonts/leaflet-serif';
import { cn } from '@app/shadcn/util/lib';
import { contrast } from '@app/utils/color-contrast';
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
    { key: 'stripes', label: 'Stripes' },
    { key: 'columns', label: 'Columns' },
    { key: 'margin', label: 'Margin' }
];

const ARTWORKS: Array<{ key: ThemeArtwork | null; label: string }> = [
    { key: null, label: 'None' },
    { key: 'marble', label: 'Marbled paper' }
];

/**
 * Where the `margin` pattern draws its rule: 56px left of the form column
 * (FORM_COLUMN, 672px, centred). On a page narrower than the column and its
 * margin the stop falls off the page, and the page is all sheet.
 */
const MARGIN_RULE_AT = 'calc(50% - 392px)';

/**
 * The one place the theme's background becomes CSS — used by the runtime page
 * ground, the mini previews and the editors alike, so what you preview is what
 * responders get. `accent` always stays underneath as the base colour (it's
 * what patterns draw on, what shows while an image loads, and the fallback for
 * incomplete gradient data).
 */
export function themeBackgroundStyle(theme?: Partial<FormTheme>, { compact = false, leftAligned = false }: { /** A small preview or swatch. */ compact?: boolean; /** A page whose column keeps to the left edge. */ leftAligned?: boolean } = {}): CSSProperties {
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
        if (bg.pattern === 'columns') {
            // Twelve columns (four on phones) between the page's side
            // margins, the form gutter (tailwind.css --form-grid-*): hairlines
            // at 20% of the tertiary, decorative, about 1.3:1 on a white page.
            // repeat-x draws one line per column edge: the side margin is
            // narrower than a column, so no line falls outside them.
            const line = `${theme?.tertiary ?? '#818CA0'}33`;
            if (compact) return { ...base, backgroundImage: `linear-gradient(90deg, ${line} 1px, transparent 1px)`, backgroundSize: '12px 100%', backgroundPosition: '6px 0' };
            return {
                ...base,
                backgroundImage: `linear-gradient(90deg, ${line} 1px, transparent 1px)`,
                backgroundSize: 'calc((100% - 2 * var(--form-grid-margin, 32px)) / var(--form-grid-columns, 12)) 100%',
                backgroundPosition: 'var(--form-grid-margin, 32px) 0',
                backgroundRepeat: 'repeat-x'
            };
        }
        if (bg.pattern === 'margin') {
            // An exercise-book page: the page colour as the margin, a hairline
            // rule in the highlight (else the tertiary), then a white sheet
            // for the questions where the ink reads on white (else the page
            // colour itself). A left-aligned column has no room for a margin.
            const sheet = isHexColour(theme?.primary) && contrast(theme!.primary!, '#FFFFFF') >= 4.5 ? '#FFFFFF' : (theme?.accent ?? '#FFFFFF');
            const rule = isHexColour(theme?.highlight) ? theme!.highlight! : (theme?.tertiary ?? '#818CA0');
            const at = compact ? '22%' : leftAligned ? '-2px' : MARGIN_RULE_AT;
            return { ...base, backgroundImage: `linear-gradient(90deg, transparent ${at}, ${rule} ${at}, ${rule} calc(${at} + 1px), ${sheet} calc(${at} + 1px))` };
        }
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
export interface ThemePreviewSample {
    /** The form's own first question, in place of "Question". */
    question?: string;
    /** One of its options, in place of "Answer". */
    answer?: string;
}

export const ThemePreview = ({ color, sample }: { color: FormTheme; /** Words from the form itself, so a thumbnail shows this form. */ sample?: ThemePreviewSample }) => {
    const { primary, secondary, tertiary } = color;
    const question = sample?.question?.trim() || 'Question';
    const answer = sample?.answer?.trim() || 'Answer';
    const tokens = styleTokens(color.style);
    if (tokens.key === 'leaflet') {
        // The Leaflet miniature: section bar with its serif numeral, a
        // numbered question over a ruled option, and the button.
        const serif = { fontFamily: leafletSerif.style.fontFamily, fontWeight: 600 };
        const { rule } = leafletColours(color);
        // The theme's faces, corners, buttons and highlight, as the Leaflet
        // form wears them (theme-root.ts); nothing for a theme without them.
        const leafletRoot = themeRootProps(color);
        return (
            <div
                {...leafletRoot.attributes}
                style={{ ...themeBackgroundStyle(color, { compact: true }), ...leafletRoot.style, ...(color.bodyFont ? { fontFamily: 'var(--font-form)' } : {}) }}
                className="flex flex-col items-stretch pb-3"
                data-testid="theme-preview-leaflet"
            >
                <span className="flex items-baseline gap-2 px-4 py-1.5 text-white" style={{ background: secondary }}>
                    <span className="text-[14px] leading-none" style={serif}>
                        1
                    </span>
                    <span className="text-[12px] leading-tight" style={serif}>
                        Section
                    </span>
                </span>
                <span className="form-title-face grid grid-cols-[20px_1fr] items-baseline px-4 pt-2 text-[12px] leading-tight font-semibold" style={{ color: primary }}>
                    <span className="text-[11px]" style={{ ...serif, color: contrast(secondary, color.accent) >= 4.5 ? secondary : primary }}>
                        1.1
                    </span>
                    <span className="line-clamp-2">{question}</span>
                </span>
                <span className="mx-4 ml-9 flex items-center gap-1.5 border-b py-1 text-[11px] leading-tight" style={{ borderColor: rule, color: primary }}>
                    <span className="h-2.5 w-2.5 rounded-full border-[1.5px] bg-white" style={{ borderColor: tertiary, ...(color.highlight || color.selection ? { borderColor: 'var(--form-highlight-edge)', background: 'var(--form-highlight-edge)' } : {}) }} aria-hidden="true" />
                    <span className="truncate">{answer}</span>
                </span>
                <span style={formButtonStyle(secondary, '2px')} className="mt-2 ml-9 self-start px-2 py-0.5 text-[10px] leading-tight font-semibold text-white">
                    Continue
                </span>
            </div>
        );
    }
    // The theme's faces, corners, button style and highlight, as the form
    // wears them (theme-root.ts); nothing for a theme without them.
    const root = themeRootProps(color);
    return (
        <div {...root.attributes} style={{ ...themeBackgroundStyle(color, { compact: true }), ...root.style, ...(color.bodyFont ? { fontFamily: 'var(--font-form)' } : {}) }} className="flex flex-col items-start gap-1.5 px-4 py-3">
            <span style={{ color: primary }} className={cn('form-title-face text-[13px] leading-tight', tokens.key === 'sheet' ? 'font-serif font-medium' : tokens.key === 'studio' ? 'font-bold tracking-tight' : 'font-semibold', 'line-clamp-2')}>
                {question}
            </span>
            {/* Answer text wears primary on a white input, exactly like the
                runtime — so an illegible combination is visible right here. */}
            <span style={{ borderColor: '#E3E3E3', color: primary, borderRadius: tokens.fieldRadius }} className="w-full truncate border bg-white px-2 py-1 text-[11px] leading-tight">
                {answer}
            </span>
            <span style={formButtonStyle(secondary, tokens.inputRadius)} className="px-2 py-0.5 text-[10px] font-semibold leading-tight text-white">
                Continue
            </span>
        </div>
    );
};

export const Swatch = ({ color }: { color: string }) => <span className="border-black-300 h-3 w-3 rounded-full border" style={{ background: color }} aria-hidden="true" />;

// WCAG contrast ratio (utils/color-contrast.ts), kept exported here for the
// theme code that already reads it from this module.
export { contrast };

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

    // The artwork beside the welcome page goes with any ground.
    const artwork = bg?.artwork ? { artwork: bg.artwork } : {};
    const setType = (nextType: ThemeBackground['type']) => {
        if (nextType === 'color') {
            onChange(bg?.artwork ? { type: 'color', artwork: bg.artwork } : undefined);
            return;
        }
        if (nextType === 'gradient') {
            onChange({ type: 'gradient', gradientFrom: bg?.gradientFrom ?? theme.accent, gradientTo: bg?.gradientTo ?? theme.secondary, gradientAngle: bg?.gradientAngle ?? 135, ...artwork });
            return;
        }
        if (nextType === 'pattern') {
            onChange({ type: 'pattern', pattern: bg?.pattern ?? 'dots', ...artwork });
            return;
        }
        onChange({ type: 'image', imageUrl: bg?.imageUrl ?? '', ...artwork });
    };
    const setArtwork = (next: ThemeArtwork | null) => {
        const { artwork: _old, ...rest } = bg ?? { type: 'color' as const };
        if (next) onChange({ ...rest, artwork: next });
        else onChange(rest.type === 'color' ? undefined : rest);
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
                <div className="grid grid-cols-3 gap-2" role="group" aria-label="Pattern">
                    {PATTERNS.map((pattern) => (
                        <button
                            key={pattern.key}
                            type="button"
                            aria-pressed={bg.pattern === pattern.key}
                            onClick={() => onChange({ ...bg, pattern: pattern.key })}
                            className={cn('flex-1 overflow-hidden rounded-md border text-center', bg.pattern === pattern.key ? 'border-brand-500 ring-1 ring-brand-500' : 'border-black-300 hover:border-black-400')}
                        >
                            <span className="block h-8 w-full" style={themeBackgroundStyle({ ...theme, background: { type: 'pattern', pattern: pattern.key } }, { compact: true })} aria-hidden="true" />
                            <span className="text-black-700 block bg-white py-1 text-[10px] font-medium">{pattern.label}</span>
                        </button>
                    ))}
                </div>
            )}

            {type === 'image' && bg?.type === 'image' && (
                <ImageUrlField value={bg.imageUrl ?? ''} onChange={(imageUrl) => onChange({ ...bg, imageUrl })} />
            )}

            <span className="text-black-700 mt-1 text-xs">Artwork</span>
            <div className="border-black-300 flex overflow-hidden rounded-md border" role="group" aria-label="Artwork">
                {ARTWORKS.map((option) => (
                    <button
                        key={option.key ?? 'none'}
                        type="button"
                        aria-pressed={(bg?.artwork ?? null) === option.key}
                        onClick={() => setArtwork(option.key)}
                        className={cn('flex-1 px-2 py-1.5 text-[11px] font-medium transition-colors', (bg?.artwork ?? null) === option.key ? 'bg-brand-100 text-brand-600' : 'text-black-600 hover:bg-black-100 bg-white')}
                    >
                        {option.label}
                    </button>
                ))}
            </div>
            <p className="text-black-600 text-[11px] leading-relaxed">Fills the picture half of a welcome or ending page set beside an image, when the page has no image of its own. Served by bettercollected itself.</p>
        </div>
    );
};
