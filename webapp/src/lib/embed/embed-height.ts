/**
 * The height a framed form page needs for the page on screen (docs/embed.md): what surrounds the page's
 * scroll area (the organisation strip, the privacy strip) plus the natural height of the page's content.
 * In embed mode the stylesheet lets the content measure itself (it no longer stretches to the frame),
 * so shrinking the frame does not change the answer: `chrome = frame - scroll area`, which is what is
 * left of the frame when the scroll area is taken out, and the content's own height is added to it.
 */
export const MIN_FRAME_HEIGHT = 240;
export const MAX_FRAME_HEIGHT = 4000;
/** Smaller changes than this are not reported (a sub-pixel rounding must not start a resize loop). */
export const HEIGHT_TOLERANCE = 2;
/** Heights are reported in steps of this many pixels: a coarser figure says less about the page. */
export const HEIGHT_STEP = 40;

export function neededHeight({ frameHeight, scrollAreaHeight, contentHeight }: { frameHeight: number; scrollAreaHeight: number; contentHeight: number }): number {
    const chrome = Math.max(0, frameHeight - scrollAreaHeight);
    const needed = Math.min(MAX_FRAME_HEIGHT, Math.max(MIN_FRAME_HEIGHT, chrome + Math.ceil(contentHeight)));
    return Math.min(MAX_FRAME_HEIGHT, Math.ceil(needed / HEIGHT_STEP) * HEIGHT_STEP);
}

/** The scroll area of the page shown for `slide`, or null while it is not on screen. */
export function scrollAreaOf(root: ParentNode, slide: number): HTMLElement | null {
    return root.querySelector<HTMLElement>(`[data-slide="${slide}"] [data-radix-scroll-area-viewport]`);
}

/** The height the page for `slide` needs, or null when it cannot be measured (not rendered yet). */
export function measureNeededHeight(root: Document, frameHeight: number, slide: number): number | null {
    const area = scrollAreaOf(root, slide);
    const content = area?.firstElementChild as HTMLElement | null | undefined;
    if (!area || !content || !area.clientHeight) return null;
    return neededHeight({ frameHeight, scrollAreaHeight: area.clientHeight, contentHeight: content.getBoundingClientRect().height });
}

/** Whether `next` differs enough from the last reported height to be worth a message. */
export function heightChanged(last: number | null, next: number): boolean {
    return last === null || Math.abs(next - last) >= HEIGHT_TOLERANCE;
}
