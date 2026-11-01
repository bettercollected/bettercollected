/**
 * The file name a `Content-Disposition` header offers (the UTF-8 form first), made
 * safe to use as a download name; undefined when it offers none. Kept apart from
 * the export helpers so the API slice can use it without importing them.
 */
export function fileNameFromDisposition(header: string | null | undefined): string | undefined {
    if (!header) return undefined;
    const encoded = /filename\*\s*=\s*UTF-8''([^;]+)/i.exec(header)?.[1];
    let name: string | undefined;
    if (encoded) {
        try {
            name = decodeURIComponent(encoded.trim());
        } catch {
            name = undefined;
        }
    }
    name ??= /filename\s*=\s*"([^"]*)"/i.exec(header)?.[1] ?? /filename\s*=\s*([^;]+)/i.exec(header)?.[1]?.trim();
    const safe = (name ?? '').replace(/[\\/:*?"<>|\u0000-\u001f]+/g, ' ').trim();
    return safe || undefined;
}
