import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { downloadFile } from './file-utils';

describe('downloadFile', () => {
    const created: string[] = [];
    let clicks: Array<{ href: string; download: string | null }>;

    beforeEach(() => {
        vi.useFakeTimers();
        created.length = 0;
        clicks = [];
        window.URL.createObjectURL = vi.fn(() => {
            const url = `blob:test/${created.length + 1}`;
            created.push(url);
            return url;
        });
        window.URL.revokeObjectURL = vi.fn();
        vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (this: HTMLAnchorElement) {
            clicks.push({ href: this.getAttribute('href') ?? '', download: this.getAttribute('download') });
        });
    });

    afterEach(() => {
        vi.useRealTimers();
        vi.unstubAllGlobals();
        vi.restoreAllMocks();
    });

    it('saves the file from the signed link under its name, and lets go of the object URL afterwards', async () => {
        vi.stubGlobal('fetch', vi.fn(async () => new Response('file body', { status: 200 })));
        await expect(downloadFile('https://files.example.com/signed/cv.pdf?sig=abc', 'cv.pdf')).resolves.toBe(true);
        expect(clicks).toEqual([{ href: 'blob:test/1', download: 'cv.pdf' }]);
        expect(document.querySelector('a[download]')).toBeNull();
        vi.advanceTimersByTime(1500);
        expect(window.URL.revokeObjectURL).toHaveBeenCalledWith('blob:test/1');
    });

    it('throws for an expired or refused link and never saves the error page as the file', async () => {
        vi.stubGlobal('fetch', vi.fn(async () => new Response('<Error>Request has expired</Error>', { status: 403 })));
        await expect(downloadFile('https://files.example.com/signed/cv.pdf?sig=old', 'cv.pdf')).rejects.toThrow('Download failed (403)');
        expect(clicks).toEqual([]);
        expect(window.URL.createObjectURL).not.toHaveBeenCalled();
    });
});
