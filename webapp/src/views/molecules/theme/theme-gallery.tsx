import { KeyboardEvent, useId, useRef } from 'react';

import { AlertTriangle, Check } from 'lucide-react';

import { FormTheme } from '@app/constants/theme';
import useBuilderTranslation from '@app/lib/hooks/use-builder-translation';
import { cn } from '@app/shadcn/util/lib';
import { themeContrastGuard } from '@app/utils/theme-contrast';

import { ThemePreview, ThemePreviewSample } from './theme-shared';

export interface ThemeGalleryEntry {
    /** Unique across the gallery ("saved:Acme", "preset:Ocean", "custom"). */
    value: string;
    label: string;
    theme: FormTheme;
}

export interface ThemeGallerySection {
    key: string;
    label: string;
    entries: ThemeGalleryEntry[];
}

/**
 * The builder's theme picker: every saved theme, preset and the custom
 * palette as a thumbnail of this form in that theme (ThemePreview, the same
 * tokens the respondent form wears, with the form's own first question).
 * One radio group: Tab reaches the chosen theme, the arrow keys move and
 * choose, so the canvas previews each theme live while switching (theme
 * changes coalesce into one undo step). A theme whose colours fail AA says
 * so on its card in words, not only with an icon; it can still be picked
 * (the contrast guard below the gallery offers the fix), but not published.
 */
export default function ThemeGallery({ sections, value, onSelect, sample }: { sections: ThemeGallerySection[]; value: string; onSelect: (value: string) => void; sample?: ThemePreviewSample }) {
    const { t } = useBuilderTranslation();
    const groupRef = useRef<HTMLDivElement>(null);
    const idBase = useId();
    const all = sections.flatMap((section) => section.entries);
    const focusable = all.some((entry) => entry.value === value) ? value : all[0]?.value;

    const move = (event: KeyboardEvent<HTMLButtonElement>, index: number) => {
        const last = all.length - 1;
        const next = { ArrowRight: index + 1, ArrowDown: index + 1, ArrowLeft: index - 1, ArrowUp: index - 1, Home: 0, End: last }[event.key];
        if (next === undefined) return;
        event.preventDefault();
        const target = next > last ? 0 : next < 0 ? last : next;
        onSelect(all[target].value);
        groupRef.current?.querySelector<HTMLButtonElement>(`[data-theme-value="${CSS.escape(all[target].value)}"]`)?.focus();
    };

    return (
        <div ref={groupRef} role="radiogroup" aria-label={t('THEME.GALLERY_LABEL')} className="flex flex-col gap-3" data-testid="theme-gallery">
            {sections
                .filter((section) => section.entries.length > 0)
                .map((section) => (
                    <div key={section.key} className="flex flex-col gap-1.5">
                        <div className="text-[11px] font-semibold tracking-wide text-black-600 uppercase">{section.label}</div>
                        <div className="grid grid-cols-2 gap-2">
                            {section.entries.map((entry) => {
                                const checked = entry.value === value;
                                const failing = themeContrastGuard(entry.theme).issues.length > 0;
                                const nameId = `${idBase}-${entry.value}-name`;
                                const flagId = `${idBase}-${entry.value}-flag`;
                                return (
                                    <button
                                        key={entry.value}
                                        type="button"
                                        role="radio"
                                        aria-checked={checked}
                                        tabIndex={entry.value === focusable ? 0 : -1}
                                        data-theme-value={entry.value}
                                        aria-labelledby={nameId}
                                        aria-describedby={failing ? flagId : undefined}
                                        onClick={() => onSelect(entry.value)}
                                        onKeyDown={(event) => move(event, all.indexOf(entry))}
                                        className={cn(
                                            'group relative flex min-w-0 flex-col overflow-hidden rounded-md border bg-white text-left transition-colors',
                                            checked ? 'border-brand-500 ring-2 ring-brand-500' : 'border-black-300 hover:border-black-500'
                                        )}
                                    >
                                        <span aria-hidden="true" className="pointer-events-none block h-[112px] overflow-hidden">
                                            <ThemePreview color={entry.theme} sample={sample} />
                                        </span>
                                        <span className="flex min-h-[32px] items-center gap-1 border-t border-t-black-300 px-2 py-1">
                                            <span id={nameId} className="min-w-0 flex-1 truncate text-[11px] font-medium text-black-800">
                                                {entry.label}
                                            </span>
                                            {checked && <Check className="h-3.5 w-3.5 shrink-0 text-brand-500" aria-hidden="true" />}
                                        </span>
                                        {failing && (
                                            <span id={flagId} className="flex items-center gap-1 bg-brand-accent-100 px-2 py-0.5 text-[10px] font-semibold text-brand-olive">
                                                <AlertTriangle className="h-3 w-3 shrink-0" aria-hidden="true" />
                                                {t('THEME.GALLERY_LOW_CONTRAST')}
                                            </span>
                                        )}
                                    </button>
                                );
                            })}
                        </div>
                    </div>
                ))}
        </div>
    );
}
