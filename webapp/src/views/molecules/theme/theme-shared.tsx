import { CSSProperties } from 'react';

import { FormTheme, ThemeBackground, ThemePattern } from '@app/constants/theme';
import { cn } from '@app/shadcn/util/lib';

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
        return { ...base, backgroundImage: `url(${JSON.stringify(bg.imageUrl)})`, backgroundSize: 'cover', backgroundPosition: 'center', backgroundRepeat: 'no-repeat' };
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
    return (
        <div style={themeBackgroundStyle(color)} className="flex flex-col items-start gap-1.5 px-4 py-3">
            <span style={{ color: primary }} className="text-[13px] font-semibold leading-tight">
                Question
            </span>
            {/* Answer text wears primary on a white input, exactly like the
                runtime — so an illegible combination is visible right here. */}
            <span style={{ borderColor: tertiary, color: primary }} className="w-full rounded border bg-white px-2 py-1 text-[11px] leading-tight">
                Answer
            </span>
            <span style={{ background: secondary }} className="rounded px-2 py-0.5 text-[10px] font-semibold leading-tight text-white">
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
        return <p className="mt-1 text-[11px] font-medium text-[#0E8A5F]">Looks legible — contrast passes everywhere it matters.</p>;
    }
    return (
        <div className="mt-1 flex flex-col gap-1 rounded-md bg-[#FBF3E4] px-2.5 py-2">
            {notes.map((note) => (
                <p key={note} className="text-[11px] leading-relaxed text-[#B26B00]">
                    {note}
                </p>
            ))}
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

            {type === 'color' && <p className="text-black-500 text-[11px] leading-relaxed">Uses the background colour above.</p>}

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
                                <span className="text-black-500 text-[11px] uppercase tabular-nums">{bg[stop.key]}</span>
                                <input type="color" aria-label={`Gradient ${stop.label.toLowerCase()} colour`} value={bg[stop.key]} onChange={(e) => onChange({ ...bg, [stop.key]: e.target.value })} className="border-black-300 h-7 w-9 cursor-pointer rounded border bg-white p-0.5" />
                            </span>
                        </div>
                    ))}
                    <div className="flex items-center justify-between gap-3">
                        <span className="text-black-700 text-xs">Angle</span>
                        <span className="flex items-center gap-2">
                            <input type="range" min={0} max={360} step={45} aria-label="Gradient angle" value={bg.gradientAngle ?? 135} onChange={(e) => onChange({ ...bg, gradientAngle: Number(e.target.value) })} className="w-24 accent-[#2456CC]" />
                            <span className="text-black-500 w-8 text-right text-[11px] tabular-nums">{bg.gradientAngle ?? 135}°</span>
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
                            className={cn('flex-1 overflow-hidden rounded-md border text-center', bg.pattern === pattern.key ? 'border-[#2456CC] shadow-[0_0_0_1px_#2456CC]' : 'border-black-300 hover:border-black-400')}
                        >
                            <span className="block h-8 w-full" style={themeBackgroundStyle({ ...theme, background: { type: 'pattern', pattern: pattern.key } })} aria-hidden="true" />
                            <span className="text-black-700 block bg-white py-1 text-[10px] font-medium">{pattern.label}</span>
                        </button>
                    ))}
                </div>
            )}

            {type === 'image' && bg?.type === 'image' && (
                <div className="flex flex-col gap-1.5">
                    <input
                        type="url"
                        aria-label="Background image URL"
                        placeholder="https://…"
                        value={bg.imageUrl ?? ''}
                        onChange={(e) => onChange({ ...bg, imageUrl: e.target.value.trim() })}
                        className="border-black-300 text-black-800 placeholder:text-black-400 focus:border-brand-500 w-full rounded-md border bg-white px-2.5 py-1.5 text-xs outline-none"
                    />
                    <p className="text-black-500 text-[11px] leading-relaxed">Paste an image address. The background colour shows while it loads.</p>
                </div>
            )}
        </div>
    );
};
