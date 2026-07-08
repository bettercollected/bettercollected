import { FormTheme } from '@app/constants/theme';

// Each editable colour, labelled by what it actually controls on the responder
// form (not by its internal role name), so the choice is legible to a creator.
export const THEME_ROLE_FIELDS: Array<{ key: 'accent' | 'primary' | 'secondary' | 'tertiary'; label: string }> = [
    { key: 'accent', label: 'Background' },
    { key: 'primary', label: 'Questions & text' },
    { key: 'secondary', label: 'Buttons' },
    { key: 'tertiary', label: 'Input borders' }
];

/**
 * An honest miniature of what the theme actually controls on the responder
 * form: question ink on the accent ground, a bordered input, a button with
 * white text. Real contrast, visible at a glance — not four abstract boxes.
 */
export const ThemePreview = ({ color }: { color: FormTheme }) => {
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
 * Live legibility read for a custom palette — the same three roles the presets
 * are held to. Non-alarmist: it tells the creator what to fix, in plain terms.
 */
export const ContrastNotes = ({ theme }: { theme: FormTheme }) => {
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
