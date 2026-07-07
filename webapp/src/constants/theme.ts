// Default = the trust palette (Design-Language.md §1): calm neutral surface,
// ink for words, one confident blue for actions. Saturated full-bleed colour
// stays available through the other themes — it's opt-in, not the default.
//
// Every theme below is contrast-verified against how the roles are actually
// used at runtime (WCAG 2.1):
//   primary   — question/answer text on the accent background   → ≥ 7:1 (AAA)
//   secondary — button fills carrying white text                → ≥ 4.5:1 (AA)
//   tertiary  — input borders / UI affordances on the accent    → ≥ 3:1 (non-text)
// A form theme that renders illegible buttons isn't a style choice, it's a
// defect — the palette passes or it doesn't ship.
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
        title: 'Blue',
        primary: '#111827',
        secondary: '#1D4ED8',
        tertiary: '#2563EB',
        accent: '#DBEAFE'
    },
    {
        title: 'Green',
        primary: '#052E16',
        secondary: '#15803D',
        tertiary: '#16A34A',
        accent: '#DCFCE7'
    },
    {
        title: 'Red',
        primary: '#450A0A',
        secondary: '#B91C1C',
        tertiary: '#DC2626',
        accent: '#FEE2E2'
    },
    {
        title: 'Black',
        primary: '#101826',
        secondary: '#101826',
        tertiary: '#767676',
        accent: '#FFFFFF'
    },
    {
        title: 'Orange',
        primary: '#431407',
        secondary: '#C2410C',
        tertiary: '#EA580C',
        accent: '#FFEDD5'
    },
    {
        title: 'Purple',
        primary: '#3B0764',
        secondary: '#7E22CE',
        tertiary: '#9333EA',
        accent: '#F3E8FF'
    },
    {
        title: 'Gray',
        primary: '#111827',
        secondary: '#4B5563',
        tertiary: '#64748B',
        accent: '#F3F4F6'
    },
    {
        title: 'Pink',
        primary: '#500724',
        secondary: '#BE185D',
        tertiary: '#DB2777',
        accent: '#FCE7F3'
    },
    {
        title: 'Indigo',
        primary: '#1E1B4B',
        secondary: '#4338CA',
        tertiary: '#4F46E5',
        accent: '#E0E7FF'
    },
    {
        title: 'Yellow',
        primary: '#422006',
        secondary: '#A16207',
        tertiary: '#B45309',
        accent: '#FEF3C7'
    },
    {
        title: 'Teal',
        primary: '#042F2E',
        secondary: '#0F766E',
        tertiary: '#0D9488',
        accent: '#CCFBF1'
    },
    {
        title: 'Cyan',
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
