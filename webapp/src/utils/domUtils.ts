export function focusElementByIdWithDelay(id: string) {
    setTimeout(() => document.getElementById(id)?.focus(), 1);
}

export function focusElementById(id: string) {
    document.getElementById(id)?.focus();
}
