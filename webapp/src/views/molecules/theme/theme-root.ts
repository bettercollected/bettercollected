import { CSSProperties, useEffect } from 'react';

import { themeFaces } from '@app/assets/fonts/theme-faces';
import { FormTheme, THEME_BUTTON_STYLES, THEME_FONTS, THEME_RADII, ThemeFontId, ThemeRadius, isHexColour } from '@app/constants/theme';
import { contrast } from '@app/utils/color-contrast';

/**
 * A theme's type, shape and highlight as CSS custom properties and data
 * attributes on the element that wears the theme (LayoutWrapper, the trust
 * strip, the theme previews), so the builder canvas, the previews and the
 * respondent page draw the same thing from one place.
 *
 * Nothing is set for a key the theme leaves out (or sets to null): the
 * components fall back to exactly what they drew before these keys existed
 * (`var(--form-radius-field, 6px)`, `var(--form-button-bg, <secondary>)`),
 * and the stylesheet rules for faces and notes only match under their data
 * attribute (tailwind.css, "Form theme type and shape"). A theme without them
 * renders as before, pixel for pixel.
 *
 * Variables (each only when its key is set):
 * - `--font-form` (bodyFont): the face of the whole form;
 * - `--form-font-title` (titleFont): titles and question labels;
 * - `--form-font-data` (dataFont): `font-mono` text such as the submission number;
 * - `--form-radius-field`, `--form-radius-card`, `--form-radius-button` (radius,
 *   buttonStyle pill);
 * - `--form-button-bg`, `--form-button-fg`, `--form-button-edge` (buttonStyle
 *   outlined), and `--form-button-hover-bg`, `--form-button-hover-fg`: an
 *   outlined button fills with its ink on hover (tailwind.css `.form-button`);
 * - `--form-highlight-*` and `--focus-ring` (highlight and selection, see
 *   highlightColours).
 */

// Public Sans as the `font-form` utility sets it (tailwind.css --font-form).
const PUBLIC_SANS = "var(--font-public-sans), ui-sans-serif, system-ui, sans-serif, 'Apple Color Emoji', 'Segoe UI Emoji', 'Segoe UI Symbol', 'Noto Color Emoji'";

/** The CSS font-family of a theme face, or undefined for an id that is not one. */
export function themeFontStack(id?: string | null): string | undefined {
    if (!id || !(THEME_FONTS as readonly string[]).includes(id)) return undefined;
    return id === 'public-sans' ? PUBLIC_SANS : themeFaces[id as Exclude<ThemeFontId, 'public-sans'>];
}

/** Corners per radius: fields, option cards and buttons alike. */
export const THEME_RADIUS_PX: Record<ThemeRadius, string> = { sharp: '0px', soft: '6px', round: '16px' };

/** WCAG 2.1 contrast of two hex colours. */
const ratio = contrast;

const pageOf = (theme?: Partial<FormTheme> | null) => (isHexColour(theme?.accent) ? theme!.accent : '#FFFFFF');
const inkOf = (theme?: Partial<FormTheme> | null) => (isHexColour(theme?.primary) ? theme!.primary : '#101828');

/** Of two inks, the one that reads best on `ground`. */
const bestOn = (ground: string, a: string, b: string) => (ratio(a, ground) >= ratio(b, ground) ? a : b);

/**
 * The colours a highlight gives, each held to WCAG 2.1 AA on what it sits on
 * (`accent`, the page), else replaced by the theme's ink. Null without a
 * valid highlight or selection: everything keeps the secondary, as before.
 *
 * The chosen answer (`edge`, `fill`, `fillInk`, `solid`, `solidInk`) wears
 * the theme's `selection` when it sets one, else the highlight; the notes
 * (`rule`, `text`) and the focus ring wear the highlight, else they keep
 * what they drew before (null). So a theme can keep its chosen answers in
 * the action colour and its rubric colour for the notes alone.
 *
 * - `edge`: the chosen option's edge and control (non-text, 3:1 on the page);
 * - `rule`: the "why we ask" rule (non-text, 3:1 on the page);
 * - `text`: the "why we ask" and "optional" labels (4.5:1 on the page);
 * - `fill`/`fillInk`: the chosen option's ground and text. A highlight that
 *   reads on the page (a dark one) tints it, as the secondary does today; a
 *   light one (a lemon) fills it, with the ink on top and the ink edge
 *   carrying the state;
 * - `solid`/`solidInk`: a solid selection (the studio style, the rating
 *   scale): the highlight filled, with white or the ink, whichever reads;
 * - `focus`: the focus ring, only where the highlight reaches 3:1 on the page
 *   (else the secondary stays, as before).
 *
 * The chosen state never rests on colour alone: the filled dot or ticked
 * box, and semibold text, stay.
 */
export function highlightColours(theme?: Partial<FormTheme> | null) {
    const highlight = isHexColour(theme?.highlight) ? theme!.highlight! : null;
    const chosen = isHexColour(theme?.selection) ? theme!.selection! : highlight;
    if (!chosen) return null;
    const page = pageOf(theme);
    const ink = inkOf(theme);
    const chosenReads = ratio(chosen, page) >= 3;
    const notes = highlight
        ? {
              rule: ratio(highlight, page) >= 3 ? highlight : ink,
              text: ratio(highlight, page) >= 4.5 ? highlight : ink,
              focus: ratio(highlight, page) >= 3 ? highlight : undefined
          }
        : null;
    return {
        edge: chosenReads ? chosen : ink,
        rule: notes?.rule,
        text: notes?.text,
        fill: chosenReads ? `${chosen}1A` : chosen,
        // a 10% tint is about the page itself for contrast
        fillInk: bestOn(chosenReads ? page : chosen, ink, '#FFFFFF'),
        solid: chosen,
        solidInk: ratio('#FFFFFF', chosen) >= 4.5 ? '#FFFFFF' : bestOn(chosen, ink, '#FFFFFF'),
        focus: notes?.focus
    };
}

/**
 * The ink of an outlined button (its text and 2px edge) on its ground, the
 * page colour: the secondary where it reads as text (4.5:1, which also
 * clears the 3:1 an edge needs), else the theme's ink.
 */
export function outlinedButtonInk(theme?: Partial<FormTheme> | null): string {
    const page = pageOf(theme);
    if (isHexColour(theme?.secondary) && ratio(theme!.secondary, page) >= 4.5) return theme!.secondary;
    return inkOf(theme);
}

export interface ThemeRootProps {
    /** Custom properties for the element's `style`. */
    style: CSSProperties;
    /** `data-form-*` attributes for the element. */
    attributes: Record<string, string>;
}

/**
 * What the element wearing `theme` sets (see the module comment). Empty for a
 * theme without type, shape or highlight. `typeOnly`: the faces alone, for
 * the trust strip, which keeps the app's own controls and focus colour.
 */
export function themeRootProps(theme?: Partial<FormTheme> | null, { typeOnly = false }: { typeOnly?: boolean } = {}): ThemeRootProps {
    const style: Record<string, string> = {};
    const attributes: Record<string, string> = {};
    if (!theme) return { style, attributes };

    const body = themeFontStack(theme.bodyFont);
    if (body) {
        attributes['data-form-body-font'] = theme.bodyFont!;
        style['--font-form'] = body;
    }
    const title = themeFontStack(theme.titleFont);
    if (title) {
        attributes['data-form-title-font'] = theme.titleFont!;
        style['--form-font-title'] = title;
    }
    const data = themeFontStack(theme.dataFont);
    if (data) {
        attributes['data-form-data-font'] = theme.dataFont!;
        style['--form-font-data'] = data;
    }
    if (theme.titleWidth === 'expanded') attributes['data-form-title-width'] = 'expanded';
    if (typeOnly) return { style: style as CSSProperties, attributes };

    if (theme.radius && (THEME_RADII as readonly string[]).includes(theme.radius)) {
        const corner = THEME_RADIUS_PX[theme.radius];
        attributes['data-form-radius'] = theme.radius;
        style['--form-radius-field'] = corner;
        style['--form-radius-card'] = corner;
        style['--form-radius-button'] = corner;
    }

    if (theme.buttonStyle && (THEME_BUTTON_STYLES as readonly string[]).includes(theme.buttonStyle)) {
        attributes['data-form-buttons'] = theme.buttonStyle;
        if (theme.buttonStyle === 'outlined') {
            const ink = outlinedButtonInk(theme);
            style['--form-button-bg'] = pageOf(theme);
            style['--form-button-fg'] = ink;
            style['--form-button-edge'] = `inset 0 0 0 2px ${ink}`;
            // Hover fills the button with its ink, the page colour on it (the
            // same pair, so the same contrast).
            style['--form-button-hover-bg'] = ink;
            style['--form-button-hover-fg'] = pageOf(theme);
        }
        if (theme.buttonStyle === 'pill') style['--form-radius-button'] = '9999px';
    }

    // A ground drawn behind the whole page (the column grid) stays out of the
    // option cards: an option at rest takes the page colour (tailwind.css).
    if (theme.background?.type === 'pattern' && theme.background.pattern === 'columns') {
        attributes['data-form-ground'] = 'columns';
        style['--form-ground-fill'] = pageOf(theme);
    }

    const highlight = highlightColours(theme);
    if (highlight) {
        style['--form-highlight-edge'] = highlight.edge;
        style['--form-highlight-fill'] = highlight.fill;
        style['--form-highlight-fill-ink'] = highlight.fillInk;
        style['--form-highlight-solid'] = highlight.solid;
        style['--form-highlight-solid-ink'] = highlight.solidInk;
        // The notes only with a highlight (a selection alone leaves them as before).
        if (highlight.text && highlight.rule) {
            attributes['data-form-highlight'] = '';
            style['--form-highlight-rule'] = highlight.rule;
            style['--form-highlight-text'] = highlight.text;
        }
        if (highlight.focus) style['--focus-ring'] = highlight.focus;
    }
    return { style: style as CSSProperties, attributes };
}

/**
 * On a respondent page, what portals out of the form (date and dropdown
 * popovers, toasts) reads its face from <body> (`respondent-typeface` in
 * tailwind.css): give <body> the theme's body face too, while the form is
 * shown. Nothing happens for a theme without one.
 */
export function useBodyFormFace(bodyFont: string | null | undefined, enabled: boolean) {
    useEffect(() => {
        const stack = enabled ? themeFontStack(bodyFont) : undefined;
        if (!stack) return;
        document.body.style.setProperty('--font-form', stack);
        return () => {
            document.body.style.removeProperty('--font-form');
        };
    }, [bodyFont, enabled]);
}

/**
 * A colour a theme variable may replace: `var(--name, fallback)`, which is
 * the fallback itself while the variable is not set. Undefined stays
 * undefined (no colour to fall back to, nothing drawn, as before).
 */
export function themed(variable: string, fallback: string | undefined): string | undefined {
    return fallback === undefined ? undefined : `var(${variable}, ${fallback})`;
}

/**
 * The style of a button painted in the form's action colour (Start,
 * Continue, Submit, the ending's button): today's fill, white text and corners unless the theme
 * says otherwise through the variables above. `corner` is the button's
 * corner without a theme radius.
 */
export function formButtonStyle(secondary: string | undefined, corner: string): CSSProperties {
    return {
        ...(secondary ? { background: `var(--form-button-bg, ${secondary})` } : {}),
        color: 'var(--form-button-fg, #FFFFFF)',
        boxShadow: 'var(--form-button-edge, none)',
        borderRadius: `var(--form-radius-button, ${corner})`
    };
}

/**
 * The builder canvas's copy of the welcome page's button: as it was until
 * the theme sets a radius or a button style, then what respondents get
 * (`formButtonStyle`, with the respondent page's corner).
 */
export function canvasButtonStyle(theme: Partial<FormTheme> | null | undefined, corner: string): CSSProperties {
    if (!theme?.radius && !theme?.buttonStyle) return { background: theme?.secondary };
    return formButtonStyle(theme?.secondary, corner);
}
