import { FormSlideLayout } from '@app/models/enums/form';

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

// `columns`: a twelve-column hairline grid (four on phones), decorative only.
// `margin`: a page set like an exercise book: a margin in the page colour, a
// hairline rule in the highlight, and a white sheet for the questions.
export type ThemePattern = 'dots' | 'grid' | 'stripes' | 'columns' | 'margin';
export const THEME_PATTERNS: ReadonlyArray<ThemePattern> = ['dots', 'grid', 'stripes', 'columns', 'margin'];

// Built-in artwork, served by the app itself (public/themes/), never from a
// third party. It fills the picture half of a welcome or ending page whose
// layout has one and no image of its own, and runs as a band along the top
// of the other pages that end the form. `marble`: a marbled endpaper.
export type ThemeArtwork = 'marble';
export const THEME_ARTWORKS: ReadonlyArray<ThemeArtwork> = ['marble'];

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
    /** Built-in artwork beside the welcome page (see THEME_ARTWORKS). Absent: none. */
    artwork?: ThemeArtwork | null;
}

export const THEME_STYLES: ReadonlyArray<ThemeStyle> = ['classic', 'sheet', 'studio', 'leaflet'];

// Type and shape. Every key is optional and its absence (or null, as stored
// forms send it) means the look forms had before these keys existed: Public
// Sans, the style's own corners, filled buttons, the secondary colour for the
// chosen answer. The faces are self-hosted (assets/fonts/theme-faces.ts) and
// load only when a form uses them. The backend keeps the same lists (common
// models/standard_form.py); a backend test fails when they drift.
export type ThemeFontId = 'public-sans' | 'atkinson-next' | 'archivo' | 'besley' | 'rubik' | 'atkinson-mono';
export type ThemeTitleWidth = 'normal' | 'expanded';
export type ThemeRadius = 'sharp' | 'soft' | 'round';
export type ThemeButtonStyle = 'filled' | 'outlined' | 'pill';

export const THEME_FONTS: ReadonlyArray<ThemeFontId> = ['public-sans', 'atkinson-next', 'archivo', 'besley', 'rubik', 'atkinson-mono'];
// `expanded` sets display titles at 125% width on a face with a width axis (Archivo).
export const THEME_TITLE_WIDTHS: ReadonlyArray<ThemeTitleWidth> = ['normal', 'expanded'];
// Corners of fields, option cards and buttons: 0, 6px, 16px.
export const THEME_RADII: ReadonlyArray<ThemeRadius> = ['sharp', 'soft', 'round'];
export const THEME_BUTTON_STYLES: ReadonlyArray<ThemeButtonStyle> = ['filled', 'outlined', 'pill'];

/** The theme keys that dress type and shape: a colour preset without them keeps the form's own. */
export const THEME_TYPE_SHAPE_KEYS = ['titleFont', 'bodyFont', 'dataFont', 'titleWidth', 'radius', 'buttonStyle'] as const;

const THEME_CHOICES: Array<[(typeof THEME_TYPE_SHAPE_KEYS)[number], ReadonlyArray<string>]> = [
    ['titleFont', THEME_FONTS],
    ['bodyFont', THEME_FONTS],
    ['dataFont', THEME_FONTS],
    ['titleWidth', THEME_TITLE_WIDTHS],
    ['radius', THEME_RADII],
    ['buttonStyle', THEME_BUTTON_STYLES]
];

/** A #rrggbb colour. */
export const isHexColour = (value: unknown): value is string => typeof value === 'string' && /^#[0-9a-fA-F]{6}$/.test(value);

/**
 * What is wrong with a theme's type, shape and highlight keys, word for word
 * as the backend says it (common models/standard_form.py `theme_problems`):
 * each is absent (or null) or one of its listed values, the highlight and
 * the selection #rrggbb, the background's artwork on its list.
 */
export function themeProblems(theme: unknown, path = 'theme'): string[] {
    if (theme == null || typeof theme !== 'object') return [];
    const value = theme as Record<string, unknown>;
    const problems: string[] = [];
    for (const [key, allowed] of THEME_CHOICES) {
        if (value[key] != null && !allowed.includes(value[key] as string)) problems.push(`${path}.${key} must be one of: ${allowed.join(', ')}.`);
    }
    if (value.highlight != null && !isHexColour(value.highlight)) problems.push(`${path}.highlight must be a 6-digit hex colour, e.g. #A3305A.`);
    if (value.selection != null && !isHexColour(value.selection)) problems.push(`${path}.selection must be a 6-digit hex colour, e.g. #1E4D3B.`);
    const background = value.background as Record<string, unknown> | null | undefined;
    if (background != null && typeof background === 'object') {
        if (background.artwork != null && !(THEME_ARTWORKS as readonly unknown[]).includes(background.artwork)) problems.push(`${path}.background.artwork must be one of: ${THEME_ARTWORKS.join(', ')}.`);
    }
    return problems;
}

/**
 * The type, shape and highlight keys a theme sets (null and absent left out),
 * for carrying them from one theme to the next in the editors.
 */
export function themeTypeShape(theme?: Partial<FormTheme> | null): Partial<FormTheme> {
    const kept: Record<string, unknown> = {};
    for (const key of [...THEME_TYPE_SHAPE_KEYS, 'highlight', 'selection'] as const) if (theme?.[key] != null) kept[key] = theme[key];
    return kept as Partial<FormTheme>;
}

export interface FormTheme {
    title: string;
    primary: string;
    secondary: string;
    tertiary: string;
    accent: string;
    background?: ThemeBackground;
    style?: ThemeStyle;
    /** Titles and question labels. */
    titleFont?: ThemeFontId | null;
    /** Everything else respondents read. */
    bodyFont?: ThemeFontId | null;
    /** Data such as the submission number (absent: the app's mono face). */
    dataFont?: ThemeFontId | null;
    titleWidth?: ThemeTitleWidth | null;
    radius?: ThemeRadius | null;
    buttonStyle?: ThemeButtonStyle | null;
    /** #rrggbb: the chosen answer, the "why we ask" and "optional" notes, the focus ring where it reads. Absent: secondary. */
    highlight?: string | null;
    /** #rrggbb: the chosen answer alone, when it should differ from the highlight. Absent: the highlight, else secondary. */
    selection?: string | null;
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
    },
    // Complete looks: colours, faces, corners, buttons and background in
    // one pick. They set every type and shape key, so nothing of the
    // previous look stays behind.
    {
        // A small-press book: Besley titles, Atkinson Hyperlegible text, a
        // cloth-green action colour, a rose rubric for notes and the margin
        // rule, and a marbled endpaper beside the welcome page. Chosen
        // answers stay in the cloth (selection) so rose never reads as an
        // error. Ink 13.9:1, edge 3.1:1, rose 5.9:1 on the blush margin.
        title: 'Kantlijn',
        primary: '#16261F',
        secondary: '#1E4D3B',
        tertiary: '#7D8C84',
        accent: '#F8EEEC',
        style: 'classic',
        titleFont: 'besley',
        bodyFont: 'atkinson-next',
        dataFont: 'atkinson-mono',
        titleWidth: 'normal',
        radius: 'soft',
        buttonStyle: 'filled',
        highlight: '#A3305A',
        selection: '#1E4D3B',
        background: {
            type: 'pattern',
            pattern: 'margin',
            artwork: 'marble'
        }
    },
    {
        // A Swiss poster: expanded Archivo titles on a visible twelve-column
        // grid, square edges, outlined buttons, and one ultramarine kept for
        // what is the respondent's own (answers, actions, the submission
        // number). Ultramarine 8.6:1 with white, edge 4.9:1 on white.
        title: 'Raster',
        primary: '#0E0E14',
        secondary: '#2B2FD1',
        tertiary: '#6D7083',
        accent: '#FFFFFF',
        style: 'studio',
        titleFont: 'archivo',
        bodyFont: 'archivo',
        dataFont: 'atkinson-mono',
        titleWidth: 'expanded',
        radius: 'sharp',
        buttonStyle: 'outlined',
        background: {
            type: 'pattern',
            pattern: 'columns'
        }
    }
];

/**
 * The welcome page layout a complete-look preset is made for: Kantlijn sets
 * the welcome page beside its artwork, Raster sets it left aligned. The
 * backend keeps the same list (constants/themes.py PRESET_WELCOME_LAYOUTS).
 */
export const PRESET_WELCOME_LAYOUTS: Readonly<Record<string, FormSlideLayout>> = {
    Kantlijn: FormSlideLayout.TWO_COLUMN_IMAGE_RIGHT,
    Raster: FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND_LEFT_ALIGN
};

const IMAGE_LAYOUTS: ReadonlyArray<string> = [FormSlideLayout.TWO_COLUMN_IMAGE_LEFT, FormSlideLayout.TWO_COLUMN_IMAGE_RIGHT, FormSlideLayout.SINGLE_COLUMN_IMAGE_BACKGROUND];

/**
 * The welcome page's layout after picking the preset `next` over the
 * theme `previous`, or undefined to leave it as it is (the backend's
 * set_theme_preset does the same, ops.py `_welcome_layout_after_preset`):
 *
 * - a welcome page with an image of its own keeps its layout;
 * - otherwise it takes the layout the preset is made for, if any;
 * - a page set beside the previous theme's artwork, which the new theme
 *   does not have, goes back to the default layout (no empty picture half).
 */
export function welcomeLayoutAfterPreset(welcomePage: { layout?: string | null; imageUrl?: string | null } | null | undefined, previous: Partial<FormTheme> | null | undefined, next: Partial<FormTheme>): FormSlideLayout | undefined {
    if (welcomePage == null || welcomePage.imageUrl?.trim()) return undefined;
    const suggested = next.title ? PRESET_WELCOME_LAYOUTS[next.title] : undefined;
    if (suggested) return welcomePage.layout === suggested ? undefined : suggested;
    if (previous?.background?.artwork && !next.background?.artwork && welcomePage.layout && IMAGE_LAYOUTS.includes(welcomePage.layout)) return FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND;
    return undefined;
}

// The backend keeps a copy of this list (backend constants/themes.py
// theme_dict) for forms the AI, the API and imports dress; this list is the
// source of truth and a backend test fails when the two drift. Keep each
// preset as plain `key: 'value'` lines (and a `background: { ... }` block
// of the same) so that test can read it.

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
