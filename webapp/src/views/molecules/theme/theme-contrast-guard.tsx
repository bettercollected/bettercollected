import { forwardRef } from 'react';

import { AlertTriangle, ArrowRight, Check, Info } from 'lucide-react';

import { FormTheme } from '@app/constants/theme';
import useBuilderTranslation from '@app/lib/hooks/use-builder-translation';
import { themeContrastGuard } from '@app/utils/theme-contrast';

import { Swatch } from './theme-shared';

const ROLES = ['accent', 'primary', 'secondary', 'tertiary'] as const;

/** A ratio as people read it: one decimal, rounded down so 4.47 never shows as 4.5. */
const formatRatio = (ratio: number, language: string) => new Intl.NumberFormat(language, { minimumFractionDigits: 1, maximumFractionDigits: 1 }).format(Math.floor(ratio * 10) / 10);

/**
 * The contrast guard of the theme editors (builder Design tab, Themes page):
 * every pairing of the theme's own colours that fails WCAG AA where the
 * respondent form shows it, with its ratio, and the nearest colours that
 * pass, applied in one click. A failing theme can't be saved or published
 * (the editors and the publish checks refuse it), so the guard says so.
 * The count is announced politely as colours change; the list is not, so a
 * screen reader isn't flooded while a colour is dragged.
 */
const ThemeContrastGuard = forwardRef<HTMLDivElement, { theme: FormTheme; onApplyFix?: (next: FormTheme) => void; id?: string }>(function ThemeContrastGuard({ theme, onApplyFix, id }, ref) {
    const { t, i18n } = useBuilderTranslation();
    const { issues, fix, imageGround } = themeContrastGuard(theme);
    const language = i18n?.language || 'en';

    if (issues.length === 0) {
        return (
            <div id={id} ref={ref} tabIndex={-1} className="mt-1 flex flex-col gap-1 outline-none" data-testid="contrast-guard">
                <p aria-live="polite" className="flex items-start gap-1.5 text-[11px] leading-relaxed font-medium text-success-700">
                    <Check className="mt-px h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                    {t('THEME.CONTRAST_PASSES')}
                </p>
                {imageGround && (
                    <p className="flex items-start gap-1.5 text-[11px] leading-relaxed text-black-700">
                        <Info className="mt-px h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                        {t('THEME.CONTRAST_IMAGE')}
                    </p>
                )}
            </div>
        );
    }

    const changed = fix ? ROLES.filter((role) => fix[role] && fix[role] !== theme[role]) : [];
    const gradientChanged = !!fix?.background && fix.background !== theme.background;

    return (
        <div id={id} ref={ref} tabIndex={-1} className="mt-1 flex flex-col gap-2 rounded-md border border-brand-accent bg-brand-accent-100 px-3 py-2.5 outline-none focus-visible:ring-2 focus-visible:ring-brand-500" data-testid="contrast-guard">
            <p aria-live="polite" className="flex items-start gap-1.5 text-xs leading-relaxed font-semibold text-black-900">
                <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-brand-olive" aria-hidden="true" />
                {t('THEME.CONTRAST_FAILS', { count: issues.length })}
            </p>
            <ul className="flex flex-col gap-1 pl-5 text-[11px] leading-relaxed text-black-800">
                {issues.map((issue) => (
                    <li key={issue.key} className="list-disc">
                        {t(`THEME.CONTRAST_ISSUE_${issue.key.toUpperCase()}`)}: <span className="tabular-nums">{t('THEME.CONTRAST_RATIO', { ratio: formatRatio(issue.ratio, language), minimum: formatRatio(issue.minimum, language) })}</span>
                    </li>
                ))}
            </ul>
            {imageGround && <p className="text-[11px] leading-relaxed text-black-700">{t('THEME.CONTRAST_IMAGE')}</p>}
            {fix && onApplyFix && (
                <div className="flex flex-col gap-1.5 border-t border-brand-accent/40 pt-2">
                    <span className="text-[11px] font-semibold text-black-700">{t('THEME.CONTRAST_SUGGESTION')}</span>
                    <ul className="flex flex-col gap-1">
                        {changed.map((role) => (
                            <li key={role} className="flex items-center gap-1.5 text-[11px] text-black-800">
                                <span className="min-w-0 flex-1 truncate">{t(`THEME.ROLE_${role.toUpperCase()}`)}</span>
                                <Swatch color={theme[role]} />
                                <ArrowRight className="h-3 w-3 text-black-600" aria-hidden="true" />
                                <Swatch color={fix[role]!} />
                                <span className="font-mono text-[10px] uppercase tabular-nums">{fix[role]}</span>
                            </li>
                        ))}
                        {gradientChanged && fix.background?.type === 'gradient' && (
                            <li className="flex items-center gap-1.5 text-[11px] text-black-800">
                                <span className="min-w-0 flex-1 truncate">{t('THEME.ROLE_GRADIENT')}</span>
                                <Swatch color={fix.background.gradientFrom!} />
                                <Swatch color={fix.background.gradientTo!} />
                            </li>
                        )}
                    </ul>
                    <button
                        type="button"
                        onClick={() => onApplyFix({ ...theme, ...fix })}
                        className="mt-0.5 self-start rounded-md border border-black-400 bg-white px-2.5 py-1.5 text-[11px] font-semibold text-black-900 transition-colors hover:bg-black-100"
                    >
                        {t('THEME.CONTRAST_APPLY')}
                    </button>
                </div>
            )}
        </div>
    );
});

export default ThemeContrastGuard;

/** Whether a theme may be saved or published: no failing pairing of its colours. */
export const themePassesContrast = (theme: FormTheme) => themeContrastGuard(theme).issues.length === 0;
