import { useMemo, useState } from 'react';

import Link from 'next/link';

import { FormTheme, THEME_TYPE_SHAPE_KEYS, ThemeColors, findPreset, themeTypeShape, welcomeLayoutAfterPreset } from '@app/constants/theme';
import useBuilderTranslation from '@app/lib/hooks/use-builder-translation';
import { FieldTypes } from '@app/models/dtos/form';
import { ScrollArea } from '@app/shadcn/components/ui/scroll-area';
import { useAppSelector } from '@app/store/hooks';
import { useBuilderActions } from '@app/store/jotai/field-selectors';
import { useFormState } from '@app/store/jotai/form';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { questionText } from '@app/utils/publish-checks';
import { themeContrastGuard } from '@app/utils/theme-contrast';
import FormLogoSettings from '@app/views/molecules/form-builder/form-logo-settings';
import ThemeContrastGuard from '@app/views/molecules/theme/theme-contrast-guard';
import ThemeGallery, { ThemeGallerySection } from '@app/views/molecules/theme/theme-gallery';
import { THEME_ROLE_FIELDS, ThemeBackgroundEditor, ThemePreviewSample, ThemeStyleEditor } from '@app/views/molecules/theme/theme-shared';
import ThemeTypeShapeEditor from '@app/views/molecules/theme/theme-type-shape-editor';

const CUSTOM_TITLE = 'Custom';

/** The id the publish checks' "Show the theme" link and the guard share. */
export const DESIGN_CONTRAST_GUARD_ID = 'design-contrast-guard';

/** The form's first question and one of its options, for the gallery's thumbnails. */
function formSample(pages: Array<any> | undefined): ThemePreviewSample {
    for (const page of pages ?? []) {
        for (const field of page?.type === FieldTypes.SLIDE ? (page?.properties?.fields ?? []) : [page]) {
            const question = field ? questionText(field) : '';
            if (!question) continue;
            const choice = (field?.properties?.choices ?? []).map((c: any) => String(c?.value || c?.label || '').trim()).find(Boolean);
            return { question: question.length > 48 ? question.slice(0, 47).trimEnd() + '…' : question, answer: choice || undefined };
        }
    }
    return {};
}

export default function PageDesignTab() {
    const { t } = useBuilderTranslation();
    const { updateFormTheme, updateWelcomePageLayout, formState, theme } = useFormState();
    const { getFormFields } = useBuilderActions();
    // Read once when the tab opens: thumbnails don't follow every keystroke.
    const sample = useMemo(() => formSample(getFormFields()), [getFormFields]);
    const workspace = useAppSelector(selectWorkspace);
    const savedThemes: FormTheme[] = workspace?.customThemes ?? [];
    const isCustom = theme?.title === CUSTOM_TITLE;

    // Seed the custom editor from whatever theme is active, so "Custom" starts
    // from a sensible place rather than empty.
    const [custom, setCustom] = useState<FormTheme>({
        title: CUSTOM_TITLE,
        primary: theme?.primary ?? ThemeColors[0].primary,
        secondary: theme?.secondary ?? ThemeColors[0].secondary,
        tertiary: theme?.tertiary ?? ThemeColors[0].tertiary,
        accent: theme?.accent ?? ThemeColors[0].accent,
        background: theme?.background,
        style: theme?.style,
        ...themeTypeShape(theme)
    });

    const applyCustom = (next: FormTheme) => {
        setCustom(next);
        updateFormTheme(next);
    };

    // Dropdown values carry their group so a saved theme may share a preset's
    // name without colliding ("saved:Ocean" vs "preset:Ocean").
    // A preset is found by its title in any case, so one the AI set shows too.
    const preset = findPreset(theme?.title);
    const selectValue = isCustom ? 'custom' : savedThemes.some((t) => t.title === theme?.title) ? `saved:${theme?.title}` : preset ? `preset:${preset.title}` : '';

    const handleSelect = (value: string) => {
        if (value === 'custom') {
            // The custom palette, in the type and shape (and highlight) the form wears now.
            const { primary, secondary, tertiary, accent, background, style } = custom;
            applyCustom({ title: CUSTOM_TITLE, primary, secondary, tertiary, accent, background, style, ...themeTypeShape(theme) });
            return;
        }
        const [group, ...rest] = value.split(':');
        const title = rest.join(':');
        const source = group === 'saved' ? savedThemes : ThemeColors;
        const picked = source.find((t) => t.title === title);
        if (!picked) return;
        // Type and shape the picked theme leaves open keep the form's own, like
        // the style (the set_theme_preset op does the same); its colours,
        // highlight included, replace the form's.
        const kept = Object.fromEntries(THEME_TYPE_SHAPE_KEYS.filter((key) => picked[key] == null && theme?.[key] != null).map((key) => [key, theme![key]]));
        const next: FormTheme = { ...structuredClone(picked), style: picked.style ?? theme?.style, ...kept };
        // A complete-look preset sets the welcome page's layout it is made
        // for (the set_theme_preset op does the same); a saved theme does not.
        const layout = group === 'preset' ? welcomeLayoutAfterPreset(formState?.welcomePage, theme, next) : undefined;
        updateFormTheme(next);
        if (layout) updateWelcomePageLayout(layout);
    };

    // What the preview shows: the active theme, whatever its source — including
    // a legacy title that no longer matches any preset (colours live on the form).
    const activeTheme: FormTheme = {
        title: theme?.title ?? ThemeColors[0].title,
        primary: theme?.primary ?? ThemeColors[0].primary,
        secondary: theme?.secondary ?? ThemeColors[0].secondary,
        tertiary: theme?.tertiary ?? ThemeColors[0].tertiary,
        accent: theme?.accent ?? ThemeColors[0].accent,
        background: theme?.background,
        style: theme?.style,
        ...themeTypeShape(theme)
    };

    const activeFails = themeContrastGuard(activeTheme).issues.length > 0;
    const sections: ThemeGallerySection[] = [
        { key: 'saved', label: t('THEME.GALLERY_SAVED'), entries: savedThemes.map((saved) => ({ value: `saved:${saved.title}`, label: saved.title, theme: saved })) },
        { key: 'presets', label: t('THEME.GALLERY_PRESETS'), entries: ThemeColors.map((preset) => ({ value: `preset:${preset.title}`, label: preset.title, theme: preset })) },
        { key: 'custom', label: t('THEME.GALLERY_ONE_OFF'), entries: [{ value: 'custom', label: t('THEME.GALLERY_CUSTOM'), theme: custom }] }
    ];

    return (
        <div className="flex h-full flex-col">
            <div className="px-4 pb-3">
                <div className="text-black-600 text-xs font-semibold uppercase tracking-wide">Theme</div>
                <p className="text-black-600 mt-1 text-xs leading-relaxed">{t('THEME.GALLERY_HINT')}</p>
            </div>
            <ScrollArea className="max-h-design-content flex-1 overflow-y-auto border-t">
                <div className="flex flex-col gap-3 p-3">
                    <ThemeGallery sections={sections} value={selectValue} onSelect={handleSelect} sample={sample} />

                    {/* Style dresses whatever theme is active — orthogonal to colours. */}
                    <ThemeStyleEditor value={theme?.style} onChange={(style) => updateFormTheme({ ...activeTheme, style })} />

                    {/* Faces, corners, buttons and highlight dress whatever theme is active too. */}
                    <ThemeTypeShapeEditor theme={isCustom ? custom : activeTheme} onChange={(next) => (isCustom ? applyCustom({ ...next, title: CUSTOM_TITLE }) : updateFormTheme(next))} />

                    {/* A picked saved theme (or a legacy one) that fails: the
                        guard offers the fix, which makes it a custom palette. */}
                    {!isCustom && activeFails && <ThemeContrastGuard id={DESIGN_CONTRAST_GUARD_ID} theme={activeTheme} onApplyFix={(next) => applyCustom({ ...next, title: CUSTOM_TITLE })} />}

                    {isCustom && (
                        <div className="flex flex-col gap-2.5 px-1">
                            {THEME_ROLE_FIELDS.map((field) => (
                                <div key={field.key} className="flex items-center justify-between gap-3">
                                    <span className="text-black-700 text-xs">{field.label}</span>
                                    <span className="flex items-center gap-2">
                                        <span className="text-black-600 text-[11px] uppercase tabular-nums">{custom[field.key]}</span>
                                        <input
                                            type="color"
                                            aria-label={field.label}
                                            value={custom[field.key]}
                                            onChange={(e) => applyCustom({ ...custom, title: CUSTOM_TITLE, [field.key]: e.target.value })}
                                            className="border-black-300 h-7 w-9 cursor-pointer rounded border bg-white p-0.5"
                                        />
                                    </span>
                                </div>
                            ))}
                            <ThemeBackgroundEditor theme={custom} onChange={(background) => applyCustom({ ...custom, title: CUSTOM_TITLE, background })} />
                            <ThemeContrastGuard id={DESIGN_CONTRAST_GUARD_ID} theme={custom} onApplyFix={(next) => applyCustom({ ...next, title: CUSTOM_TITLE })} />
                        </div>
                    )}

                    {/* Where themes are made: the workspace Themes page. */}
                    <p className="text-black-600 border-t-black-300 border-t pt-3 text-[11px] leading-relaxed">
                        Save your own palette to reuse across forms on the{' '}
                        <Link href={`/${workspace?.workspaceName}/dashboard/themes`} className="text-brand-500 hover:text-brand-600 font-medium underline underline-offset-2">
                            Themes page
                        </Link>
                        .
                    </p>

                    <div className="border-t-black-300 border-t pt-4">
                        <FormLogoSettings />
                    </div>
                </div>
            </ScrollArea>
        </div>
    );
}
