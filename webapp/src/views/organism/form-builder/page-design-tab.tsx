import { useState } from 'react';

import Link from 'next/link';

import { FormTheme, ThemeColors } from '@app/constants/theme';
import { ScrollArea } from '@app/shadcn/components/ui/scroll-area';
import { Select, SelectContent, SelectGroup, SelectItem, SelectLabel, SelectTrigger, SelectValue } from '@app/shadcn/components/ui/select';
import { useAppSelector } from '@app/store/hooks';
import { useFormState } from '@app/store/jotai/form';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { ContrastNotes, Swatch, THEME_ROLE_FIELDS, ThemeBackgroundEditor, ThemePreview, ThemeStyleEditor } from '@app/views/molecules/theme/theme-shared';

const CUSTOM_TITLE = 'Custom';

export default function PageDesignTab() {
    const { updateFormTheme, theme } = useFormState();
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
        style: theme?.style
    });

    const applyCustom = (next: FormTheme) => {
        setCustom(next);
        updateFormTheme(next);
    };

    // Dropdown values carry their group so a saved theme may share a preset's
    // name without colliding ("saved:Ocean" vs "preset:Ocean").
    const selectValue = isCustom ? 'custom' : savedThemes.some((t) => t.title === theme?.title) ? `saved:${theme?.title}` : ThemeColors.some((t) => t.title === theme?.title) ? `preset:${theme?.title}` : '';

    const handleSelect = (value: string) => {
        if (value === 'custom') {
            applyCustom({ ...custom, title: CUSTOM_TITLE });
            return;
        }
        const [group, ...rest] = value.split(':');
        const title = rest.join(':');
        const source = group === 'saved' ? savedThemes : ThemeColors;
        const picked = source.find((t) => t.title === title);
        if (picked) updateFormTheme({ ...picked, style: picked.style ?? theme?.style });
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
        style: theme?.style
    };

    return (
        <div className="flex h-full flex-col">
            <div className="px-4 pb-3">
                <div className="text-black-600 text-xs font-semibold uppercase tracking-wide">Theme</div>
                <p className="text-black-600 mt-1 text-xs leading-relaxed">Every preset meets WCAG AA contrast for questions, buttons and inputs.</p>
            </div>
            <ScrollArea className="max-h-design-content flex-1 overflow-y-auto border-t">
                <div className="flex flex-col gap-3 p-3">
                    <Select value={selectValue} onValueChange={handleSelect}>
                        <SelectTrigger aria-label="Pick a theme by name" className="border-black-300 h-9 w-full bg-white text-xs">
                            <SelectValue placeholder="Pick a theme…" />
                        </SelectTrigger>
                        <SelectContent className="z-[100000] bg-white">
                            {savedThemes.length > 0 && (
                                <SelectGroup>
                                    <SelectLabel className="text-black-500 text-[11px] font-semibold uppercase tracking-wide">Your themes</SelectLabel>
                                    {savedThemes.map((saved) => (
                                        <SelectItem key={`saved:${saved.title}`} value={`saved:${saved.title}`} className="text-xs">
                                            <span className="flex items-center gap-2">
                                                <Swatch color={saved.secondary} />
                                                {saved.title}
                                            </span>
                                        </SelectItem>
                                    ))}
                                </SelectGroup>
                            )}
                            <SelectGroup>
                                <SelectLabel className="text-black-500 text-[11px] font-semibold uppercase tracking-wide">Presets</SelectLabel>
                                {ThemeColors.map((preset) => (
                                    <SelectItem key={`preset:${preset.title}`} value={`preset:${preset.title}`} className="text-xs">
                                        <span className="flex items-center gap-2">
                                            <Swatch color={preset.secondary} />
                                            {preset.title}
                                        </span>
                                    </SelectItem>
                                ))}
                            </SelectGroup>
                            <SelectGroup>
                                <SelectLabel className="text-black-500 text-[11px] font-semibold uppercase tracking-wide">One-off</SelectLabel>
                                <SelectItem value="custom" className="text-xs">
                                    <span className="flex items-center gap-2">
                                        <Swatch color={custom.secondary} />
                                        Custom — pick your own colours
                                    </span>
                                </SelectItem>
                            </SelectGroup>
                        </SelectContent>
                    </Select>

                    {/* Style dresses whatever theme is active — orthogonal to colours. */}
                    <ThemeStyleEditor value={theme?.style} onChange={(style) => updateFormTheme({ ...activeTheme, style })} />

                    {/* Only the selected theme is previewed — the dropdown is the
                        catalogue; this shows what the form actually wears. */}
                    <div className="border-black-300 overflow-hidden rounded-lg border">
                        <ThemePreview color={isCustom ? custom : activeTheme} />
                        <div className="border-t-black-200 flex items-center justify-between border-t bg-white px-3 py-2">
                            <span className="text-black-800 truncate text-xs font-medium">{isCustom ? 'Custom' : activeTheme.title}</span>
                            <span className="flex shrink-0 gap-1">
                                <Swatch color={(isCustom ? custom : activeTheme).primary} />
                                <Swatch color={(isCustom ? custom : activeTheme).secondary} />
                                <Swatch color={(isCustom ? custom : activeTheme).accent} />
                            </span>
                        </div>
                    </div>

                    {isCustom && (
                        <div className="flex flex-col gap-2.5 px-1">
                            {THEME_ROLE_FIELDS.map((field) => (
                                <div key={field.key} className="flex items-center justify-between gap-3">
                                    <span className="text-black-700 text-xs">{field.label}</span>
                                    <span className="flex items-center gap-2">
                                        <span className="text-black-500 text-[11px] uppercase tabular-nums">{custom[field.key]}</span>
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
                            <ContrastNotes theme={custom} />
                        </div>
                    )}

                    {/* Where themes are made: the workspace Themes page. */}
                    <p className="text-black-600 border-t-black-200 border-t pt-3 text-[11px] leading-relaxed">
                        Save your own palette to reuse across forms on the{' '}
                        <Link href={`/${workspace?.workspaceName}/dashboard/themes`} className="text-brand-500 hover:text-brand-600 font-medium underline underline-offset-2">
                            Themes page
                        </Link>
                        .
                    </p>
                </div>
            </ScrollArea>
        </div>
    );
}
