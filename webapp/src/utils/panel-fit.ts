/**
 * Whether the privacy panel may open by default without pushing the page's
 * primary action (the welcome page's Start button) out of view.
 *
 * The form area is the space above the trust strip. Opening the panel takes
 * `panelHeight` from it; the content (from its first element through the
 * primary action, plus the page's vertical padding) must still fit in what
 * is left. Content shorter than the area is centred or top-aligned; either
 * way it fits exactly when its height does.
 */
export function panelFits({ contentHeight, paddingY, formAreaHeight, panelHeight }: { contentHeight: number; paddingY: number; formAreaHeight: number; panelHeight: number }): boolean {
    return contentHeight + paddingY <= formAreaHeight - panelHeight;
}

/**
 * Measures the page for `panelFits`: the content box marked
 * `[data-primary-content]` through the button marked `[data-primary-action]`,
 * the padding of the box around it, and the area marked `[data-fit-area]`.
 * `openPanelHeight` is the height of the panel when it is already open (it
 * has taken that space from the area). A page without a primary action has
 * nothing to protect.
 */
export function measurePrimaryActionFit(root: Document, { panelHeight, openPanelHeight }: { panelHeight: number; openPanelHeight: number }): boolean {
    const action = root.querySelector<HTMLElement>('[data-primary-action]');
    const content = root.querySelector<HTMLElement>('[data-primary-content]');
    const area = root.querySelector<HTMLElement>('[data-fit-area]');
    if (!action || !content || !area) return true;
    const gutter = content.parentElement;
    const style = gutter ? getComputedStyle(gutter) : null;
    const paddingY = style ? (parseFloat(style.paddingTop) || 0) + (parseFloat(style.paddingBottom) || 0) : 0;
    return panelFits({
        contentHeight: action.getBoundingClientRect().bottom - content.getBoundingClientRect().top,
        paddingY,
        formAreaHeight: area.clientHeight + openPanelHeight,
        panelHeight
    });
}
