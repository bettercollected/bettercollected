import { useState } from 'react';

import { Check } from 'lucide-react';

import { FormTheme, ThemeColors } from '@app/constants/theme';
import { ScrollArea } from '@app/shadcn/components/ui/scroll-area';
import { Select, SelectContent, SelectGroup, SelectItem, SelectLabel, SelectTrigger, SelectValue } from '@app/shadcn/components/ui/select';
import { cn } from '@app/shadcn/util/lib';
import { selectAuth } from '@app/store/auth/slice';
import { useAppSelector } from '@app/store/hooks';
import { useFormState } from '@app/store/jotai/form';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { ContrastNotes, Swatch, THEME_ROLE_FIELDS, ThemePreview } from '@app/views/molecules/theme/theme-shared';

const CUSTOM_TITLE = 'Custom';

export default function PageDesignTab() {
    const { updateFormTheme, theme } = useFormState();
    const authState = useAppSelector(selectAuth);
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
        accent: theme?.accent ?? ThemeColors[0].accent
    });

    const applyCustom = (next: FormTheme) => {
        setCustom(next);
        updateFormTheme(next);
    };

    // Dropdown values carry their group so a saved theme may share a preset's
    // name without colliding ("saved:Ocean" vs "preset:Ocean").
    const selectValue = savedThemes.some((t) => t.title === theme?.title) ? `saved:${theme?.title}` : ThemeColors.some((t) => t.title === theme?.title) ? `preset:${theme?.title}` : '';

    const handleSelect = (value: string) => {
        const [group, ...rest] = value.split(':');
        const title = rest.join(':');
        const source = group === 'saved' ? savedThemes : ThemeColors;
        const picked = source.find((t) => t.title === title);
        if (picked) updateFormTheme({ ...picked });
    };

    const ThemeCard = ({ themeColor, selected, onClick }: { themeColor: FormTheme; selected: boolean; onClick: () => void }) => (
        <button
            type="button"
            data-umami-event={'Update New Theme Button'}
            data-umami-event-email={authState.email}
            onClick={onClick}
            aria-pressed={selected}
            className={cn(
                'w-full overflow-hidden rounded-lg border text-left transition-colors focus-visible:outline-none',
                selected ? 'border-[#2456CC] shadow-[0_0_0_1px_#2456CC]' : 'border-black-300 hover:border-black-400 focus-visible:border-[#2456CC]'
            )}
        >
            <ThemePreview color={themeColor} />
            <div className="border-t-black-200 flex items-center justify-between border-t bg-white px-3 py-2">
                <span className="text-black-800 truncate text-xs font-medium">{themeColor.title}</span>
                {selected ? (
                    <Check className="h-3.5 w-3.5 shrink-0 text-[#2456CC]" strokeWidth={2.5} aria-hidden="true" />
                ) : (
                    <span className="flex shrink-0 gap-1">
                        <Swatch color={themeColor.primary} />
                        <Swatch color={themeColor.secondary} />
                        <Swatch color={themeColor.accent} />
                    </span>
                )}
            </div>
        </button>
    );

    return (
        <div className="flex h-full flex-col">
            <div className="flex flex-col gap-3 px-4 pb-3">
                <div>
                    <div className="text-black-600 text-xs font-semibold uppercase tracking-wide">Theme</div>
                    <p className="text-black-600 mt-1 text-xs leading-relaxed">Every preset meets WCAG AA contrast for questions, buttons and inputs.</p>
                </div>
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
                    </SelectContent>
                </Select>
            </div>
            <ScrollArea className="max-h-design-content flex-1 overflow-y-auto border-t">
                <div className="flex flex-col gap-2 p-3">
                    {savedThemes.length > 0 && (
                        <>
                            <div className="text-black-500 px-1 text-[11px] font-semibold uppercase tracking-wide">Your themes</div>
                            {savedThemes.map((saved) => (
                                <ThemeCard key={`saved-card-${saved.title}`} themeColor={saved} selected={theme?.title === saved.title} onClick={() => updateFormTheme({ ...saved })} />
                            ))}
                            <div className="text-black-500 mt-2 px-1 text-[11px] font-semibold uppercase tracking-wide">Presets</div>
                        </>
                    )}
                    {ThemeColors.map((themeColor) => (
                        <ThemeCard key={themeColor.title} themeColor={themeColor} selected={theme?.title === themeColor.title} onClick={() => updateFormTheme(themeColor)} />
                    ))}

                    {/* Custom — the creator's own palette. Same honest preview as the
                        presets, plus a live contrast read since a custom palette
                        isn't guaranteed to be legible. */}
                    <div className="border-t-black-200 mt-2 flex flex-col gap-3 border-t pt-4">
                        <ThemeCard themeColor={custom} selected={isCustom} onClick={() => applyCustom({ ...custom, title: CUSTOM_TITLE })} />

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
                                <ContrastNotes theme={custom} />
                            </div>
                        )}
                    </div>
                </div>
            </ScrollArea>
        </div>
    );
}
