import { useState } from 'react';

import { Check } from 'lucide-react';

import { FormTheme, ThemeColors } from '@app/constants/theme';
import { ScrollArea } from '@app/shadcn/components/ui/scroll-area';
import { cn } from '@app/shadcn/util/lib';
import { selectAuth } from '@app/store/auth/slice';
import { useAppSelector } from '@app/store/hooks';
import { useFormState } from '@app/store/jotai/form';

const CUSTOM_TITLE = 'Custom';

// Each editable colour, labelled by what it actually controls on the responder
// form (not by its internal role name), so the choice is legible to a creator.
const CUSTOM_FIELDS: Array<{ key: 'accent' | 'primary' | 'secondary' | 'tertiary'; label: string }> = [
    { key: 'accent', label: 'Background' },
    { key: 'primary', label: 'Questions & text' },
    { key: 'secondary', label: 'Buttons' },
    { key: 'tertiary', label: 'Input borders' }
];

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
                                {CUSTOM_FIELDS.map((field) => (
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

/**
 * An honest miniature of what the theme actually controls on the responder
 * form: question ink on the accent ground, a bordered input, a button with
 * white text. Real contrast, visible at a glance — not four abstract boxes.
 */
const ThemePreview = ({ color }: { color: FormTheme }) => {
    const { primary, secondary, tertiary, accent } = color;
    return (
        <div style={{ background: accent }} className="flex flex-col items-start gap-1.5 px-4 py-3">
            <span style={{ color: primary }} className="text-[13px] font-semibold leading-tight">
                Question
            </span>
            <span style={{ borderColor: tertiary }} className="w-full rounded border bg-white px-2 py-1 text-[11px] leading-tight text-[#657085]">
                Answer
            </span>
            <span style={{ background: secondary }} className="rounded px-2 py-0.5 text-[10px] font-semibold leading-tight text-white">
                Continue
            </span>
        </div>
    );
};

const Swatch = ({ color }: { color: string }) => <span className="border-black-300 h-3 w-3 rounded-full border" style={{ background: color }} aria-hidden="true" />;

// Relative luminance + contrast ratio (WCAG 2.1). Native <input type="color">
// always yields a 6-digit hex, so no short-hex handling is needed here.
function luminance(hex: string): number {
    const c = hex.replace('#', '');
    const channels = [0, 2, 4]
        .map((i) => parseInt(c.substring(i, i + 2), 16) / 255)
        .map((v) => (v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4)));
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2];
}

function contrast(a: string, b: string): number {
    const l1 = luminance(a);
    const l2 = luminance(b);
    return (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);
}

/**
 * Live legibility read for a custom palette — the same three roles the presets
 * are held to. Non-alarmist: it tells the creator what to fix, in plain terms.
 */
const ContrastNotes = ({ theme }: { theme: FormTheme }) => {
    const notes: string[] = [];
    if (contrast(theme.primary, theme.accent) < 4.5) notes.push('Question text may be hard to read on this background.');
    if (contrast('#FFFFFF', theme.secondary) < 4.5) notes.push('White button text may be hard to read on this button colour.');
    if (contrast(theme.tertiary, theme.accent) < 3) notes.push('Input outlines may be hard to see on this background.');

    if (notes.length === 0) {
        return <p className="mt-1 text-[11px] font-medium text-[#0E8A5F]">Looks legible — contrast passes on all three.</p>;
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
