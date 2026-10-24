// What can take keyboard focus inside a question; elements taken out of the
// tab order (tabindex="-1", such as the unchosen options of a radio group)
// are skipped below.
const FOCUSABLE = 'input:not([type="hidden"]):not([disabled]), textarea:not([disabled]), select:not([disabled]), button:not([disabled]), a[href], [tabindex]';

/**
 * The control a respondent lands on in a question: a radio group's single
 * tab stop (the chosen option, else the first), else the first control in
 * the tab order (a text field, a checkbox, the date or dropdown trigger).
 */
export function firstControlIn(question: Element | null): HTMLElement | null {
    if (!question) return null;
    const radio = question.querySelector<HTMLElement>('[role="radio"][tabindex="0"]');
    if (radio) return radio;
    return Array.from(question.querySelectorAll<HTMLElement>(FOCUSABLE)).find((element) => element.tabIndex >= 0) ?? null;
}

/**
 * Bring a question into view in the page's scroll container.
 *
 * Focus moves to the question's text field when it has one (as before). With
 * `focusControl` (a question that failed validation) any other question's
 * first control takes focus too, so keyboard and screen reader users land on
 * the question and hear its error (WCAG 3.3.1, 2.4.3). Focus is otherwise
 * left where it is: it is never dropped to the page.
 */
export function scrollToDivById(divId: string = '', scrollableDivId: string = 'questions-container', { focusControl = false }: { focusControl?: boolean } = {}) {
    const targetDiv = document.getElementById(divId);
    if (targetDiv) {
        const scrollableDiv = document.getElementById(scrollableDivId);
        const centerOffset = (scrollableDiv?.clientHeight || 0) / 2;

        const divOffset = targetDiv.offsetTop;
        const divHeight = targetDiv.clientHeight;

        const scrollToOffset = divOffset > centerOffset ? divOffset - centerOffset + divHeight / 2 : 0;

        // Not every environment can scroll an element (jsdom has no scrollTo);
        // focusing the field below still takes the respondent there.
        if (typeof scrollableDiv?.scrollTo === 'function') {
            const reduceMotion = typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
            scrollableDiv.scrollTo({
                top: scrollToOffset,
                behavior: reduceMotion ? 'auto' : 'smooth'
            });
        }
        const next = document.getElementById(`input-field-${divId}`) ?? (focusControl ? firstControlIn(targetDiv) : null);
        next?.focus();
    }
}

/** A question inside a repeating group item: into view, and its first control focused. */
export function focusQuestionInGroup(scopedId: string) {
    const question = document.getElementById(scopedId);
    question?.scrollIntoView?.({ behavior: 'smooth', block: 'center' });
    firstControlIn(question)?.focus({ preventScroll: true });
}
