'use client';

import { useEffect, useId, useRef } from 'react';

import { useTranslation } from 'react-i18next';

import { FormTheme, THEME_FONTS, ThemeButtonStyle, ThemeFontId, ThemeRadius, isHexColour } from '@app/constants/theme';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@app/shadcn/components/ui/select';
import { cn } from '@app/shadcn/util/lib';

import { themeFontStack } from './theme-root';

/** Each face by its own name (a name, so not translated). */
export const THEME_FONT_NAMES: Record<ThemeFontId, string> = {
    'public-sans': 'Public Sans',
    'atkinson-next': 'Atkinson Hyperlegible Next',
    archivo: 'Archivo',
    besley: 'Besley',
    rubik: 'Rubik',
    'atkinson-mono': 'Atkinson Hyperlegible Mono'
};

const DEFAULT = 'default';
const RADII: Array<{ key: ThemeRadius | typeof DEFAULT; label: string }> = [
    { key: DEFAULT, label: 'THEME.RADIUS_DEFAULT' },
    { key: 'sharp', label: 'THEME.RADIUS_SHARP' },
    { key: 'soft', label: 'THEME.RADIUS_SOFT' },
    { key: 'round', label: 'THEME.RADIUS_ROUND' }
];
const BUTTONS: Array<{ key: ThemeButtonStyle; label: string }> = [
    { key: 'filled', label: 'THEME.BUTTON_FILLED' },
    { key: 'outlined', label: 'THEME.BUTTON_OUTLINED' },
    { key: 'pill', label: 'THEME.BUTTON_PILL' }
];

// The colours the editor sets: the highlight, and the chosen answer's own.
const COLOUR_KEYS = ['highlight', 'selection'] as const;
type ColourKey = (typeof COLOUR_KEYS)[number];

const segment = (on: boolean) => cn('flex-1 px-2 py-1.5 text-[11px] font-medium transition-colors', on ? 'bg-brand-100 text-brand-600' : 'text-black-600 hover:bg-black-100 bg-white');

/** A face option, set in that face (the builder loads it from the app; respondents only get the faces their form uses). */
const FaceName = ({ id, suffix }: { id: ThemeFontId; suffix?: string }) => (
    <span style={{ fontFamily: themeFontStack(id) }}>
        {THEME_FONT_NAMES[id]}
        {suffix ? ` ${suffix}` : ''}
    </span>
);

/**
 * Type, shape and highlight of the active theme, for the theme editors (the
 * builder's Design tab and the Themes page): title, text and data faces, wide
 * titles, corners, button style, highlight and chosen-answer colours. Choosing the default of
 * a key removes it, so a theme left at the defaults stays exactly as forms
 * were before these keys existed.
 */
export default function ThemeTypeShapeEditor({ theme, onChange }: { theme: FormTheme; onChange: (theme: FormTheme) => void }) {
    const { t } = useTranslation('builder');
    const ids = useId();
    const set = (patch: Partial<FormTheme>) => {
        const next: Record<string, unknown> = { ...theme, ...patch };
        for (const [key, value] of Object.entries(patch)) if (value == null) delete next[key];
        // Wide titles only exist in Archivo: a title face that is not it drops the setting.
        if ((next.titleFont ?? next.bodyFont) !== 'archivo') delete next.titleWidth;
        onChange(next as unknown as FormTheme);
    };
    // Adding or removing a colour (highlight, chosen answer) swaps the control
    // that was pressed for another: keyboard focus moves to it (the colour
    // input after adding, the add button after removing) instead of falling
    // back to the page.
    const colourRefs = useRef<Partial<Record<ColourKey, HTMLInputElement | null>>>({});
    const addRefs = useRef<Partial<Record<ColourKey, HTMLButtonElement | null>>>({});
    const focusNext = useRef<{ key: ColourKey; to: 'colour' | 'add' } | null>(null);
    useEffect(() => {
        const next = focusNext.current;
        if (!next) return;
        const target = next.to === 'colour' ? colourRefs.current[next.key] : addRefs.current[next.key];
        if (!target) return;
        focusNext.current = null;
        target.focus();
    }, [theme.highlight, theme.selection]);
    const titleFace = theme.titleFont ?? theme.bodyFont;
    const radius = theme.radius ?? DEFAULT;
    const buttons = theme.buttonStyle ?? 'filled';

    return (
        <div className="flex flex-col gap-3">
            <span className="text-xs font-semibold text-black-700">{t('THEME.HEADING')}</span>

            <div className="flex flex-col gap-1">
                <span id={`${ids}-title`} className="text-xs text-black-700">
                    {t('THEME.TITLE_FONT')}
                </span>
                <Select value={theme.titleFont ?? DEFAULT} onValueChange={(value) => set({ titleFont: value === DEFAULT ? null : (value as ThemeFontId) })}>
                    <SelectTrigger aria-labelledby={`${ids}-title`} aria-describedby={`${ids}-title-hint`} className="h-9 w-full border-control bg-white text-xs">
                        <SelectValue />
                    </SelectTrigger>
                    <SelectContent className="bg-white">
                        <SelectItem value={DEFAULT} className="text-xs">
                            {t('THEME.TITLE_FONT_DEFAULT')}
                        </SelectItem>
                        {THEME_FONTS.map((id) => (
                            <SelectItem key={id} value={id} className="text-sm">
                                <FaceName id={id} />
                            </SelectItem>
                        ))}
                    </SelectContent>
                </Select>
                <p id={`${ids}-title-hint`} className="text-[11px] leading-relaxed text-black-600">
                    {t('THEME.TITLE_FONT_HINT')}
                </p>
            </div>

            <div className="flex flex-col gap-1">
                <span id={`${ids}-body`} className="text-xs text-black-700">
                    {t('THEME.BODY_FONT')}
                </span>
                <Select value={theme.bodyFont ?? 'public-sans'} onValueChange={(value) => set({ bodyFont: value === 'public-sans' ? null : (value as ThemeFontId) })}>
                    <SelectTrigger aria-labelledby={`${ids}-body`} aria-describedby={`${ids}-body-hint`} className="h-9 w-full border-control bg-white text-xs">
                        <SelectValue />
                    </SelectTrigger>
                    <SelectContent className="bg-white">
                        {THEME_FONTS.map((id) => (
                            <SelectItem key={id} value={id} className="text-sm">
                                <FaceName id={id} suffix={id === 'public-sans' ? t('THEME.FONT_DEFAULT_SUFFIX') : undefined} />
                            </SelectItem>
                        ))}
                    </SelectContent>
                </Select>
                <p id={`${ids}-body-hint`} className="text-[11px] leading-relaxed text-black-600">
                    {t('THEME.BODY_FONT_HINT')}
                </p>
            </div>

            <div className="flex flex-col gap-1">
                <span id={`${ids}-data`} className="text-xs text-black-700">
                    {t('THEME.DATA_FONT')}
                </span>
                <Select value={theme.dataFont ?? DEFAULT} onValueChange={(value) => set({ dataFont: value === DEFAULT ? null : (value as ThemeFontId) })}>
                    <SelectTrigger aria-labelledby={`${ids}-data`} aria-describedby={`${ids}-data-hint`} className="h-9 w-full border-control bg-white text-xs">
                        <SelectValue />
                    </SelectTrigger>
                    <SelectContent className="bg-white">
                        <SelectItem value={DEFAULT} className="text-xs">
                            {t('THEME.DATA_FONT_DEFAULT')}
                        </SelectItem>
                        {THEME_FONTS.map((id) => (
                            <SelectItem key={id} value={id} className="text-sm">
                                <FaceName id={id} />
                            </SelectItem>
                        ))}
                    </SelectContent>
                </Select>
                <p id={`${ids}-data-hint`} className="text-[11px] leading-relaxed text-black-600">
                    {t('THEME.DATA_FONT_HINT')}
                </p>
            </div>

            {/* Only Archivo has a wide cut: the switch shows where it does something. */}
            {titleFace === 'archivo' && (
                <label className="flex items-start gap-2 text-xs">
                    <input
                        type="checkbox"
                        className="mt-0.5 h-4 w-4 shrink-0 cursor-pointer rounded-[4px]"
                        checked={theme.titleWidth === 'expanded'}
                        onChange={(event) => set({ titleWidth: event.target.checked ? 'expanded' : null })}
                        aria-describedby={`${ids}-wide-hint`}
                    />
                    <span className="flex flex-col gap-0.5">
                        <span className="text-black-700">{t('THEME.WIDE_TITLES')}</span>
                        <span id={`${ids}-wide-hint`} className="text-[11px] leading-relaxed text-black-600">
                            {t('THEME.WIDE_TITLES_HINT')}
                        </span>
                    </span>
                </label>
            )}

            <div className="flex flex-col gap-1">
                <span id={`${ids}-radius`} className="text-xs text-black-700">
                    {t('THEME.RADIUS')}
                </span>
                <div className="flex overflow-hidden rounded-md border border-black-300" role="group" aria-labelledby={`${ids}-radius`} aria-describedby={`${ids}-radius-hint`}>
                    {RADII.map((option) => (
                        <button key={option.key} type="button" aria-pressed={radius === option.key} onClick={() => set({ radius: option.key === DEFAULT ? null : option.key })} className={segment(radius === option.key)}>
                            {t(option.label)}
                        </button>
                    ))}
                </div>
                <p id={`${ids}-radius-hint`} className="text-[11px] leading-relaxed text-black-600">
                    {t('THEME.RADIUS_HINT')}
                </p>
            </div>

            <div className="flex flex-col gap-1">
                <span id={`${ids}-buttons`} className="text-xs text-black-700">
                    {t('THEME.BUTTONS')}
                </span>
                <div className="flex overflow-hidden rounded-md border border-black-300" role="group" aria-labelledby={`${ids}-buttons`}>
                    {BUTTONS.map((option) => (
                        <button key={option.key} type="button" aria-pressed={buttons === option.key} onClick={() => set({ buttonStyle: option.key === 'filled' ? null : option.key })} className={segment(buttons === option.key)}>
                            {t(option.label)}
                        </button>
                    ))}
                </div>
                {buttons === 'outlined' && <p className="text-[11px] leading-relaxed text-black-600">{t('THEME.BUTTONS_HINT_OUTLINED')}</p>}
            </div>

            {COLOUR_KEYS.map((key) => {
                const value = theme[key];
                const prefix = key === 'highlight' ? 'THEME.HIGHLIGHT' : 'THEME.SELECTION';
                return (
                    <div key={key} className="flex flex-col gap-1">
                        <div className="flex items-center justify-between gap-3">
                            <span id={`${ids}-${key}`} className="text-xs text-black-700">
                                {t(prefix)}
                            </span>
                            {value ? (
                                <span className="flex items-center gap-2">
                                    <span className="text-[11px] text-black-600 uppercase tabular-nums">{value}</span>
                                    <input
                                        ref={(element) => {
                                            colourRefs.current[key] = element;
                                        }}
                                        type="color"
                                        aria-labelledby={`${ids}-${key}`}
                                        value={value}
                                        onChange={(event) => set({ [key]: event.target.value.toUpperCase() })}
                                        className="h-7 w-9 cursor-pointer rounded border border-black-300 bg-white p-0.5"
                                    />
                                </span>
                            ) : (
                                <button
                                    ref={(element) => {
                                        addRefs.current[key] = element;
                                    }}
                                    type="button"
                                    onClick={() => {
                                        focusNext.current = { key, to: 'colour' };
                                        set({ [key]: (isHexColour(theme.secondary) ? theme.secondary : '#1649E2').toUpperCase() });
                                    }}
                                    className="text-[11px] font-medium text-brand-500 underline underline-offset-2 hover:text-brand-600"
                                >
                                    {t(`${prefix}_ADD`)}
                                </button>
                            )}
                        </div>
                        <p className="text-[11px] leading-relaxed text-black-600">{value ? t(`${prefix}_HINT`) : t(`${prefix}_NONE`)}</p>
                        {value && (
                            <button
                                type="button"
                                onClick={() => {
                                    focusNext.current = { key, to: 'add' };
                                    set({ [key]: null });
                                }}
                                className="self-start text-[11px] font-medium text-black-700 underline underline-offset-2 hover:text-black-900"
                            >
                                {t(`${prefix}_REMOVE`)}
                            </button>
                        )}
                    </div>
                );
            })}
        </div>
    );
}
