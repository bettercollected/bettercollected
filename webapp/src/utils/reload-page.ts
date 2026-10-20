/**
 * Reloads the current page. Its own module so a test can replace it: jsdom's
 * `window.location` cannot be redefined under every test pool.
 */
export function reloadPage(): void {
    window.location.reload();
}
