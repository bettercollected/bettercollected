import localFont from 'next/font/local';

/**
 * The Leaflet style's one serif, for section numerals, section titles and
 * question numbers; everything respondents read stays in Public Sans.
 *
 * The file comes from @fontsource/source-serif-4 (OFL-1.1) in node_modules, so
 * the build never fetches from Google, and next/font serves it from the app (no
 * request to Google when a form loads). `preload: false` keeps it off every
 * page's preload list: the browser fetches the file only when a Leaflet form
 * draws a glyph in it.
 */
export const leafletSerif = localFont({
    src: '../../../node_modules/@fontsource/source-serif-4/files/source-serif-4-latin-600-normal.woff2',
    weight: '600',
    style: 'normal',
    display: 'swap',
    preload: false,
    fallback: ['Georgia', 'Times New Roman', 'serif'],
    // Google's serif fonts size their generated fallback against Times New Roman.
    adjustFontFallback: 'Times New Roman'
});
