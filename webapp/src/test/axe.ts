import axe from 'axe-core';

/** The axe tags for WCAG 2.0 and 2.1, levels A and AA. */
export const WCAG_A_AA = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'];

/**
 * Best-practice rules held too on whole pages, for the page structure they
 * check: every part of the page in a landmark, one main, headings in order,
 * named dialogs. (axe leaves "one main" and "one h1" incomplete in jsdom, so
 * page tests assert those themselves.)
 */
export const PAGE_STRUCTURE_RULES = [
    'region',
    'landmark-one-main',
    'landmark-no-duplicate-main',
    'landmark-main-is-top-level',
    'landmark-contentinfo-is-top-level',
    'landmark-unique',
    'page-has-heading-one',
    'heading-order',
    'empty-heading',
    'aria-dialog-name'
];

/**
 * axe's WCAG 2.0/2.1 A and AA violations in `context`, as
 * "rule (impact): elements", for `expect(...).toEqual([])`. With `page`, the
 * page-structure rules above count too (for a whole page, not a component).
 *
 * jsdom has no layout, so axe cannot measure colour contrast; it reports it
 * as incomplete, not as a violation. utils/theme-contrast.test.ts checks the
 * theme presets' contrast from their colour values instead.
 */
export async function axeViolations(context: Element | Document = document, { page = false }: { page?: boolean } = {}): Promise<string[]> {
    const results = await axe.run(context, {
        runOnly: { type: 'tag', values: page ? [...WCAG_A_AA, 'best-practice'] : WCAG_A_AA },
        // The document's title and language come from the Next.js layout,
        // which component tests do not render (respondent-document-language
        // tests cover the language).
        rules: { 'document-title': { enabled: false }, 'html-has-lang': { enabled: false } },
        resultTypes: ['violations']
    });
    return results.violations.filter((v) => v.tags.some((tag) => WCAG_A_AA.includes(tag)) || PAGE_STRUCTURE_RULES.includes(v.id)).map((v) => `${v.id} (${v.impact}): ${v.nodes.map((n) => n.target.join(' ')).join(' | ')}`);
}
