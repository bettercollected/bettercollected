import { Source_Serif_4 } from 'next/font/google';

/**
 * The Leaflet style's one serif, for section numerals, section titles and
 * question numbers; everything respondents read stays in Public Sans.
 *
 * next/font downloads it at build time and serves it from the app (no request
 * to Google when a form loads). `preload: false` keeps it off every page's
 * preload list: the browser fetches the file only when a Leaflet form draws
 * a glyph in it.
 */
export const leafletSerif = Source_Serif_4({ subsets: ['latin'], weight: ['600'], display: 'swap', preload: false, fallback: ['Georgia', 'Times New Roman', 'serif'] });
