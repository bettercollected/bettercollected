export function scrollToDivById(divId: string = '', scrollableDivId: string = 'questions-container') {
    const targetDiv = document.getElementById(divId);
    if (targetDiv) {
        const scrollableDiv = document.getElementById(scrollableDivId);
        const centerOffset = (scrollableDiv?.clientHeight || 0) / 2;

        const divOffset = targetDiv.offsetTop;
        const divHeight = targetDiv.clientHeight;

        const scrollToOffset = divOffset > centerOffset ? divOffset - centerOffset + divHeight / 2 : 0;

        scrollableDiv?.scrollTo({
            top: scrollToOffset,
            behavior: 'smooth'
        });
        const activeElement = document.activeElement as HTMLLIElement;
        activeElement?.blur();
        document?.getElementById(`input-field-${divId}`)?.focus();
    }
}
