export function scrollToDivById(divId: string = '', scrollableDivId: string = 'questions-container') {
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
        const activeElement = document.activeElement as HTMLLIElement;
        activeElement?.blur();
        document?.getElementById(`input-field-${divId}`)?.focus();
    }
}
