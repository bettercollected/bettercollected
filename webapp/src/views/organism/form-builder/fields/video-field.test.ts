import { describe, expect, it } from 'vitest';

import { toEmbedUrl } from './video-field';

describe('toEmbedUrl', () => {
    it('turns a schemeless YouTube watch URL into a playable embed URL', () => {
        expect(toEmbedUrl('www.youtube.com/watch?v=abc123')).toBe('https://www.youtube.com/embed/abc123');
    });

    it('does not double the scheme when the href already has one (old bug: https://https://…)', () => {
        expect(toEmbedUrl('https://www.youtube.com/watch?v=abc123')).toBe('https://www.youtube.com/embed/abc123');
    });

    it('handles youtu.be short links', () => {
        expect(toEmbedUrl('https://youtu.be/abc123')).toBe('https://www.youtube.com/embed/abc123');
    });

    it('handles Vimeo links', () => {
        expect(toEmbedUrl('https://vimeo.com/12345678')).toBe('https://player.vimeo.com/video/12345678');
    });

    it('leaves other hosts untouched, even when the URL contains "watch" (old bug: naive replace)', () => {
        expect(toEmbedUrl('https://example.com/watchtower/video.mp4')).toBe('https://example.com/watchtower/video.mp4');
    });

    it('adds a scheme to bare hosts and returns empty for missing href', () => {
        expect(toEmbedUrl('example.com/clip')).toBe('https://example.com/clip');
        expect(toEmbedUrl(undefined)).toBe('');
        expect(toEmbedUrl('')).toBe('');
    });
});
