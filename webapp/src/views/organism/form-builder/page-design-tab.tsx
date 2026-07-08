import { useState } from 'react';

import { Check } from 'lucide-react';

import { FormTheme, ThemeColors } from '@app/constants/theme';
import { ContrastNotes, Swatch, THEME_ROLE_FIELDS, ThemePreview } from '@app/views/molecules/theme/theme-shared';
import { ScrollArea } from '@app/shadcn/components/ui/scroll-area';
import { cn } from '@app/shadcn/util/lib';
import { selectAuth } from '@app/store/auth/slice';
import { useAppSelector } from '@app/store/hooks';
import { useFormState } from '@app/store/jotai/form';

const CUSTOM_TITLE = 'Custom';


export default function PageDesignTab() {
    const { updateFormTheme, theme } = useFormState();
    const authState = useAppSelector(selectAuth);
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

    return (
        <div className="flex h-full flex-col">
            <div className="px-4 pb-3">
                <div className="text-black-600 text-xs font-semibold uppercase tracking-wide">Theme</div>
                <p className="text-black-600 mt-1 text-xs leading-relaxed">Every preset meets WCAG AA contrast for questions, buttons and inputs.</p>
            </div>
            <ScrollArea className="max-h-design-content flex-1 overflow-y-auto border-t">
                <div className="flex flex-col gap-2 p-3">
                    {ThemeColors.map((themeColor) => {
                        const selected = theme?.title === themeColor.title;
                        return (
                            <button
                                key={themeColor.title}
                                type="button"
                                data-umami-event={'Update New Theme Button'}
                                data-umami-event-email={authState.email}
                                onClick={() => updateFormTheme(themeColor)}
                                aria-pressed={selected}
                                className={cn(
                                    'w-full overflow-hidden rounded-lg border text-left transition-colors focus-visible:outline-none',
                                    selected ? 'border-[#2456CC] shadow-[0_0_0_1px_#2456CC]' : 'border-black-300 hover:border-black-400 focus-visible:border-[#2456CC]'
                                )}
                            >
                                <ThemePreview color={themeColor} />
                                <div className="border-t-black-200 flex items-center justify-between border-t bg-white px-3 py-2">
                                    <span className="text-black-800 text-xs font-medium">{themeColor.title}</span>
                                    {selected ? (
                                        <Check className="h-3.5 w-3.5 text-[#2456CC]" strokeWidth={2.5} aria-hidden="true" />
                                    ) : (
                                        <span className="flex gap-1">
                                            <Swatch color={themeColor.primary} />
                                            <Swatch color={themeColor.secondary} />
                                            <Swatch color={themeColor.accent} />
                                        </span>
                                    )}
                                </div>
                            </button>
                        );
                    })}

                    {/* Custom — the creator's own palette. Same honest preview as the
                        presets, plus a live contrast read since a custom palette
                        isn't guaranteed to be legible. */}
                    <div className="border-t-black-200 mt-2 flex flex-col gap-3 border-t pt-4">
                        <button
                            type="button"
                            onClick={() => applyCustom({ ...custom, title: CUSTOM_TITLE })}
                            aria-pressed={isCustom}
                            className={cn(
                                'w-full overflow-hidden rounded-lg border text-left transition-colors focus-visible:outline-none',
                                isCustom ? 'border-[#2456CC] shadow-[0_0_0_1px_#2456CC]' : 'border-black-300 hover:border-black-400 focus-visible:border-[#2456CC]'
                            )}
                        >
                            <ThemePreview color={custom} />
                            <div className="border-t-black-200 flex items-center justify-between border-t bg-white px-3 py-2">
                                <span className="text-black-800 text-xs font-medium">Custom</span>
                                {isCustom ? (
                                    <Check className="h-3.5 w-3.5 text-[#2456CC]" strokeWidth={2.5} aria-hidden="true" />
                                ) : (
                                    <span className="flex gap-1">
                                        <Swatch color={custom.primary} />
                                        <Swatch color={custom.secondary} />
                                        <Swatch color={custom.accent} />
                                    </span>
                                )}
                            </div>
                        </button>

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
