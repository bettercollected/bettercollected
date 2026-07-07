import { Check } from 'lucide-react';

import { FormTheme, ThemeColors } from '@app/constants/theme';
import { ScrollArea } from '@app/shadcn/components/ui/scroll-area';
import { cn } from '@app/shadcn/util/lib';
import { selectAuth } from '@app/store/auth/slice';
import { useAppSelector } from '@app/store/hooks';
import { useFormState } from '@app/store/jotai/form';

export default function PageDesignTab() {
    const { updateFormTheme, theme } = useFormState();
    const authState = useAppSelector(selectAuth);
    return (
        <div className="flex h-full flex-col">
            <div className="px-4 pb-3">
                <div className="text-black-600 text-xs font-semibold uppercase tracking-wide">Theme</div>
                <p className="text-black-600 mt-1 text-xs leading-relaxed">Every theme meets WCAG AA contrast for questions, buttons and inputs.</p>
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
