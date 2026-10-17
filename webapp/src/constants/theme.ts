// Default = the Sireto palette (DESIGN.md, Form themes): paper-mist surface,
// ink for words, one confident blue for actions. Saturated full-bleed colour
// stays available through the other themes — it's opt-in, not the default.
//
// Every theme below is contrast-verified against how the roles are actually
// used at runtime (WCAG 2.1):
//   primary   — question text on the accent background         → ≥ 7:1 (AAA)
//   primary   — answer text inside the WHITE input boxes        → ≥ 4.5:1 (AA)
//               (inputs are always white at runtime, so a dark page with light
//               ink cannot work with a single primary — no dark preset until
//               the theme model grows a separate input-text role)
//   secondary — button fills carrying white text                → ≥ 4.5:1 (AA)
//   tertiary  — input borders / UI affordances on the accent    → ≥ 3:1 (non-text)
// A form theme that renders illegible buttons isn't a style choice, it's a
// defect — the palette passes or it doesn't ship.
//
// Themes are named for what they evoke, not their hue ("Ocean", not "Blue") —
// names are how they're picked from the dropdown and the Themes page. Colour
// values are stored inline on the form, so renaming a preset never changes an
// already-published form.
export const ThemeColor = {
    accent: '#F5F7FB',
    tertiary: '#818CA0',
    secondary: '#1649E2',
    primary: '#101828'
};

// How the form is DRESSED, independent of its colours/background. 'classic'
// is today's look; 'sheet' sets questions like a printed document (serif
// labels, margin numerals, ruled rows); 'studio' is the bold graphic register
// (ghost numerals, heavy type, square edges, solid selection); 'leaflet' reads
// like a plain-language information leaflet (numbered section bars, n.m
// question numbers in a margin column, ruled options, margin-note reasons).
// Structural styles (two-pane ledger, conversational receipts) can join this
// enum once the renderer grows those modes — the model is deliberately open.
export type ThemeStyle = 'classic' | 'sheet' | 'studio' | 'leaflet';

export type ThemePattern = 'dots' | 'grid' | 'stripes';

// Optional decoration for the page ground. `accent` stays the base colour
// everywhere (inputs, sticky surfaces, fallbacks) — the background only
// dresses the page itself. Absent (or type 'color') = plain accent.
export interface ThemeBackground {
    type: 'color' | 'gradient' | 'pattern' | 'image';
    gradientFrom?: string;
    gradientTo?: string;
    gradientAngle?: number;
    pattern?: ThemePattern;
    imageUrl?: string;
}

export const THEME_STYLES: ReadonlyArray<ThemeStyle> = ['classic', 'sheet', 'studio', 'leaflet'];

export interface FormTheme {
    title: string;
    primary: string;
    secondary: string;
    tertiary: string;
    accent: string;
    background?: ThemeBackground;
    style?: ThemeStyle;
}

export const ThemeColors: Array<FormTheme> = [
    {
        title: 'Default',
        primary: '#101828',
        secondary: '#1649E2',
        tertiary: '#818CA0',
        accent: '#F5F7FB'
    },
    {
        // Warm cream ground with espresso ink — the "printed page" look.
        title: 'Paper',
        primary: '#292524',
        secondary: '#7C2D12',
        tertiary: '#78716C',
        accent: '#FAF6F0'
    },
    {
        // White sheet, near-black ink, deep navy for section bars and
        // buttons, a slate control edge (4.3:1 on white). Picking it also
        // switches the form to the Leaflet style it was made for.
        title: 'Leaflet',
        primary: '#1A1A1A',
        secondary: '#0B3D91',
        tertiary: '#6B7A99',
        accent: '#FFFFFF',
        style: 'leaflet'
    },
    {
        title: 'Ocean',
        primary: '#111827',
        secondary: '#1D4ED8',
        tertiary: '#2563EB',
        accent: '#DBEAFE'
    },
    {
        title: 'Forest',
        primary: '#052E16',
        secondary: '#15803D',
        tertiary: '#16A34A',
        accent: '#DCFCE7'
    },
    {
        title: 'Cherry',
        primary: '#450A0A',
        secondary: '#B91C1C',
        tertiary: '#DC2626',
        accent: '#FEE2E2'
    },
    {
        title: 'Mono',
        primary: '#101826',
        secondary: '#101826',
        tertiary: '#767676',
        accent: '#FFFFFF'
    },
    {
        title: 'Sunset',
        primary: '#431407',
        secondary: '#C2410C',
        tertiary: '#EA580C',
        accent: '#FFEDD5'
    },
    {
        title: 'Lavender',
        primary: '#3B0764',
        secondary: '#7E22CE',
        tertiary: '#9333EA',
        accent: '#F3E8FF'
    },
    {
        title: 'Slate',
        primary: '#111827',
        secondary: '#4B5563',
        tertiary: '#64748B',
        accent: '#F3F4F6'
    },
    {
        title: 'Blossom',
        primary: '#500724',
        secondary: '#BE185D',
        tertiary: '#DB2777',
        accent: '#FCE7F3'
    },
    {
        title: 'Twilight',
        primary: '#1E1B4B',
        secondary: '#4338CA',
        tertiary: '#4F46E5',
        accent: '#E0E7FF'
    },
    {
        title: 'Honey',
        primary: '#422006',
        secondary: '#A16207',
        tertiary: '#B45309',
        accent: '#FEF3C7'
    },
    {
        title: 'Mint',
        primary: '#042F2E',
        secondary: '#0F766E',
        tertiary: '#0D9488',
        accent: '#CCFBF1'
    },
    {
        title: 'Sky',
        primary: '#083344',
        secondary: '#0E7490',
        tertiary: '#0891B2',
        accent: '#CFFAFE'
    },
    {
        title: 'Rose',
        primary: '#4C0519',
        secondary: '#BE123C',
        tertiary: '#E11D48',
        accent: '#FFE4E6'
    }
];

// The backend keeps a copy of this list (backend constants/themes.py
// theme_dict) for forms the AI, the API and imports dress; this list is the
// source of truth and a backend test fails when the two drift. Keep each
// preset as plain `key: 'value'` lines so that test can read it.

/**
 * The preset a form's theme was picked as, by its title (any case): what the
 * builder's picker shows as selected. A preset set by the AI carries the
 * preset's own title, so it shows here too. A legacy title that names no
 * preset any more (colours live on the form) matches none.
 */
export function findPreset(title?: string | null): FormTheme | undefined {
    const key = title?.trim().toLowerCase();
    if (!key) return undefined;
    return ThemeColors.find((preset) => preset.title.toLowerCase() === key);
}

// New forms start with the Leaflet preset (and so the Leaflet style) unless
// they bring a theme of their own: a form made from a template, or a copy,
// keeps its source's. The backend gives forms made without one (AI, API,
// imports) the same preset (backend constants/themes.py NEW_FORM_THEME); a
// test keeps the two together. Stored forms never change: their theme is
// stored inline, and one without a theme still renders as Default.
export const NEW_FORM_THEME_TITLE = 'Leaflet';

/** A fresh copy of the theme new forms start with. */
export function newFormTheme(): FormTheme {
    const preset = ThemeColors.find((theme) => theme.title === NEW_FORM_THEME_TITLE) ?? ThemeColors[0];
    return { ...preset };
}
