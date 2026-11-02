/** Whole-page navigation, in one place so that tests can stand in for it (jsdom cannot navigate). */
export function reloadPage(): void {
    window.location.reload();
}

export function navigateTo(path: string): void {
    window.location.assign(path);
}
