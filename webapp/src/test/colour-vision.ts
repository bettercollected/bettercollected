// Colour-vision helpers for the tests of the app themes' chart series (daybreak-tokens.test.ts, app-theme.test.ts).
//
// Method: the Machado et al. (2009) matrices at full severity (protanopia, deuteranopia), applied to linear sRGB; the
// simulated colour is then compared with CIE76 ΔE in CIE Lab (D65). Luminance ratios are the WCAG relative-luminance
// ratio (`contrast` in utils/color-contrast). Hue and saturation are HSL.

export const PROTANOPIA = [
    [0.152286, 1.052583, -0.204868],
    [0.114503, 0.786281, 0.099216],
    [-0.003882, -0.048116, 1.051998]
];
export const DEUTERANOPIA = [
    [0.367322, 0.860646, -0.227968],
    [0.280085, 0.672501, 0.047413],
    [-0.01182, 0.04294, 0.968881]
];

export const toRgb = (hex: string) => [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255);
export const toLinear = (c: number) => (c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
export const fromLinear = (c: number) => {
    const v = Math.max(0, Math.min(1, c));
    return v <= 0.0031308 ? 12.92 * v : 1.055 * v ** (1 / 2.4) - 0.055;
};

export function toLab(linear: number[]): number[] {
    const [r, g, b] = linear;
    const f = (t: number) => (t > 0.008856 ? Math.cbrt(t) : 7.787 * t + 16 / 116);
    const x = f((0.4124 * r + 0.3576 * g + 0.1805 * b) / 0.95047);
    const y = f(0.2126 * r + 0.7152 * g + 0.0722 * b);
    const z = f((0.0193 * r + 0.1192 * g + 0.9505 * b) / 1.08883);
    return [116 * y - 16, 500 * (x - y), 200 * (y - z)];
}

/** CIE76 ΔE between two hex colours, as seen by a viewer with the given colour-vision matrix (none: normal vision). */
export function deltaE(a: string, b: string, matrix?: number[][]): number {
    const lab = (hex: string) => {
        const linear = toRgb(hex).map(toLinear);
        return toLab(matrix ? matrix.map((row) => row.reduce((sum, m, j) => sum + m * linear[j], 0)).map((c) => toLinear(fromLinear(c))) : linear);
    };
    const [x, y] = [lab(a), lab(b)];
    return Math.hypot(x[0] - y[0], x[1] - y[1], x[2] - y[2]);
}

export function hueAndSaturation(hex: string): { hue: number; saturation: number } {
    const [r, g, b] = toRgb(hex);
    const max = Math.max(r, g, b);
    const min = Math.min(r, g, b);
    const d = max - min;
    const l = (max + min) / 2;
    const saturation = d === 0 ? 0 : d / (1 - Math.abs(2 * l - 1));
    let hue = 0;
    if (d !== 0) hue = (max === r ? ((g - b) / d) % 6 : max === g ? (b - r) / d + 2 : (r - g) / d + 4) * 60;
    return { hue: (hue + 360) % 360, saturation };
}

export const hueDistance = (a: string, b: string) => {
    const d = Math.abs(hueAndSaturation(a).hue - hueAndSaturation(b).hue) % 360;
    return Math.min(d, 360 - d);
};

/** The thresholds the app themes' series are held to (DESIGN.md, "Charts"). */
export const NEIGHBOUR_LUMINANCE = 1.3; // the relative-luminance ratio of series i and i+1
export const SECOND_NEIGHBOUR_LUMINANCE = 1.5; // ... of series i and i+2
export const SIMULATED_DELTA_E = 40; // CIE76 ΔE of series i and i+1, and i and i+2, for deuteranopia and protanopia
export const DANGER_DELTA_E = 40; // CIE76 ΔE of every series from `bad`, for normal vision
export const DANGER_HUE = 30; // ... and its hue distance from `bad` in degrees, unless it is a neutral (saturation under 0.2)
