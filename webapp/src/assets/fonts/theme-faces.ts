import localFont from 'next/font/local';

/**
 * The faces a form theme can pick besides Public Sans (constants/theme.ts
 * THEME_FONTS): Atkinson Hyperlegible Next, Archivo, Besley, Rubik and
 * Atkinson Hyperlegible Mono.
 *
 * Each comes from its @fontsource-variable package (OFL-1.1, see
 * webapp/THIRD_PARTY_NOTICES.md) in node_modules, latin subset, as one
 * variable file, so the build never fetches from Google and next/font serves
 * the file from the app: no request to a third party when a form loads.
 * `preload: false` keeps every face off the pages' preload lists, so the
 * browser fetches a file only when a form draws a glyph in that face. A form
 * on today's look (no titleFont, bodyFont or dataFont) fetches none of them.
 */
const atkinsonNext = localFont({
    src: '../../../node_modules/@fontsource-variable/atkinson-hyperlegible-next/files/atkinson-hyperlegible-next-latin-wght-normal.woff2',
    weight: '200 800',
    style: 'normal',
    display: 'swap',
    preload: false,
    fallback: ['ui-sans-serif', 'system-ui', 'sans-serif'],
    adjustFontFallback: 'Arial'
});

// The width axis file (62% to 125%), so an expanded title is the real
// expanded design, not a stretched one.
const archivo = localFont({
    src: '../../../node_modules/@fontsource-variable/archivo/files/archivo-latin-wdth-normal.woff2',
    weight: '100 900',
    style: 'normal',
    display: 'swap',
    preload: false,
    declarations: [{ prop: 'font-stretch', value: '62% 125%' }],
    fallback: ['ui-sans-serif', 'system-ui', 'sans-serif'],
    adjustFontFallback: 'Arial'
});

// With its italic: margin notes and numerals in a serif title face are often set in it.
const besley = localFont({
    src: [
        { path: '../../../node_modules/@fontsource-variable/besley/files/besley-latin-wght-normal.woff2', weight: '400 900', style: 'normal' },
        { path: '../../../node_modules/@fontsource-variable/besley/files/besley-latin-wght-italic.woff2', weight: '400 900', style: 'italic' }
    ],
    display: 'swap',
    preload: false,
    fallback: ['Georgia', 'Times New Roman', 'serif'],
    adjustFontFallback: 'Times New Roman'
});

const rubik = localFont({
    src: '../../../node_modules/@fontsource-variable/rubik/files/rubik-latin-wght-normal.woff2',
    weight: '300 900',
    style: 'normal',
    display: 'swap',
    preload: false,
    fallback: ['ui-sans-serif', 'system-ui', 'sans-serif'],
    adjustFontFallback: 'Arial'
});

// Tells 0 from O and 1 from l and I: what a submission number needs.
const atkinsonMono = localFont({
    src: '../../../node_modules/@fontsource-variable/atkinson-hyperlegible-mono/files/atkinson-hyperlegible-mono-latin-wght-normal.woff2',
    weight: '200 800',
    style: 'normal',
    display: 'swap',
    preload: false,
    fallback: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'Consolas', 'monospace'],
    adjustFontFallback: false
});

/** next/font's family name (with its fallbacks) of each face, by theme font id. */
export const themeFaces = {
    'atkinson-next': atkinsonNext.style.fontFamily,
    archivo: archivo.style.fontFamily,
    besley: besley.style.fontFamily,
    rubik: rubik.style.fontFamily,
    'atkinson-mono': atkinsonMono.style.fontFamily
};
