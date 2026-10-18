/**
 * WCAG 2.x colour contrast, for hex colours (#rgb, #rrggbb). Plain
 * functions with no React, so theme previews, the builder's legibility notes
 * and tests share one formula.
 */

/** Minimum contrast for body text (WCAG 1.4.3, AA). */
export const AA_TEXT = 4.5;
/** Minimum contrast for control edges, focus and icons (WCAG 1.4.11, AA). */
export const AA_NON_TEXT = 3;

/**
 * The 0–255 channels of a #rgb or #rrggbb colour, or null when it is neither.
 * An #rrggbbaa colour gives its colour channels (the alpha is not blended).
 */
export function hexChannels(hex: string): [number, number, number] | null {
    const match = /^#?([0-9a-f]{3}|[0-9a-f]{6}|[0-9a-f]{8})$/i.exec(hex?.trim() ?? '');
    if (!match) return null;
    const digits = match[1].length === 3 ? match[1].replace(/./g, (d) => d + d) : match[1].slice(0, 6);
    return [0, 2, 4].map((i) => parseInt(digits.substring(i, i + 2), 16)) as [number, number, number];
}

/** Relative luminance (0 black to 1 white); NaN for a colour that is not hex. */
export function relativeLuminance(hex: string): number {
    const channels = hexChannels(hex);
    if (!channels) return NaN;
    const [r, g, b] = channels.map((c) => c / 255).map((v) => (v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4)));
    return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

/**
 * Contrast ratio of two colours, 1 to 21, in either order. NaN when either is
 * not a hex colour, so every `>=` check on it fails.
 */
export function contrast(a: string, b: string): number {
    const l1 = relativeLuminance(a);
    const l2 = relativeLuminance(b);
    return (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);
}
