// Default = the trust palette (Design-Language.md §1): calm neutral surface,
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
    accent: '#F6F8FC',
    tertiary: '#818CA0',
    secondary: '#2456CC',
    primary: '#101826'
};

export interface FormTheme {
    title: string;
    primary: string;
    secondary: string;
    tertiary: string;
    accent: string;
}

export const ThemeColors: Array<FormTheme> = [
    {
        title: 'Default',
        primary: '#101826',
        secondary: '#2456CC',
        tertiary: '#818CA0',
        accent: '#F6F8FC'
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
