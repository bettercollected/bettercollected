/**
 * Heading levels a text block (FieldTypes.TEXT) may use, and their styles.
 * Tailwind's reset makes h1–h3 look like body text, so the canvas and the
 * respondent form share these classes to show the same hierarchy.
 */
export const TEXT_BLOCK_HEADING_LEVELS = [1, 2, 3] as const;
export type TextBlockHeadingLevel = (typeof TEXT_BLOCK_HEADING_LEVELS)[number];

export const HEADING_CLASSES =
    '[&_h1]:text-[32px] [&_h1]:font-bold [&_h1]:leading-tight ' + '[&_h2]:text-[26px] [&_h2]:font-bold [&_h2]:leading-tight ' + '[&_h3]:text-[21px] [&_h3]:font-semibold [&_h3]:leading-snug ' + '[&_h1+*]:mt-2 [&_h2+*]:mt-2 [&_h3+*]:mt-1';
