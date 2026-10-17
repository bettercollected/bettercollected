import { describe, expect, it } from 'vitest';

import { themeBackgroundStyle } from '@app/views/molecules/theme/theme-shared';

import { firstPartyImageProps, firstPartyImageUrl, isUnsplashRouteUrl, unsplashRouteBase, unsplashRouteLoader, unsplashRouteUrl } from './first-party-image';

const API = 'https://forms.example.org/api/v1';
const ROUTE = `${API}/images/unsplash/`;

describe('Unsplash photos are loaded from our server', () => {
    it("rewrites the picker's raw address, dropping Unsplash's tracking options", () => {
        expect(unsplashRouteUrl('https://images.unsplash.com/photo-1500530855697-b586d89ba3ee?ixid=M3w&ixlib=rb-4.0.3', API)).toBe(`${ROUTE}photo-1500530855697-b586d89ba3ee`);
    });

    it("keeps the AI image search's sizing options", () => {
        expect(unsplashRouteUrl('https://images.unsplash.com/photo-1?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&ixid=M3w&ixlib=rb-4.0.3&q=80&w=1080', API)).toBe(`${ROUTE}photo-1?crop=entropy&fit=max&fm=jpg&q=80&w=1080`);
    });

    it.each([
        'http://images.unsplash.com/photo-1',
        'https://images.unsplash.com.evil.test/photo-1',
        'https://evil.test/images.unsplash.com/photo-1',
        'https://user@images.unsplash.com/photo-1',
        'https://images.unsplash.com:8443/photo-1',
        'https://images.unsplash.com/a/b/c',
        'https://images.unsplash.com/',
        'not a url'
    ])('leaves anything else alone: %s', (url) => {
        expect(unsplashRouteUrl(url, API)).toBeNull();
    });

    it('rewrites stored Unsplash addresses at render time and keeps everything else', () => {
        const ours = 'https://cdn.example.org/bucket/public/media/ws/1.jpg';
        expect(firstPartyImageUrl(ours, API)).toBe(ours);
        expect(firstPartyImageUrl('', API)).toBe('');
        expect(firstPartyImageUrl(undefined, API)).toBe('');
        expect(firstPartyImageUrl('https://images.unsplash.com/photo-1', API)).toBe(`${ROUTE}photo-1`);
    });

    it('sizes route images through the route itself', () => {
        expect(unsplashRouteLoader({ src: `${ROUTE}photo-1?fit=crop`, width: 640, quality: 60 })).toBe(`${ROUTE}photo-1?fit=crop&w=640&q=60`);
        expect(unsplashRouteLoader({ src: `${ROUTE}photo-1?w=1080&q=80`, width: 750 })).toBe(`${ROUTE}photo-1?w=750&q=75`);
    });

    it('gives next/image the route address and its loader, with the configured API host', () => {
        const props = firstPartyImageProps('https://images.unsplash.com/photo-1');
        expect(props.src).toBe(`${unsplashRouteBase()}photo-1`);
        expect(isUnsplashRouteUrl(props.src)).toBe(true);
        expect(props.loader).toBe(unsplashRouteLoader);
        expect(firstPartyImageProps('https://cdn.example.org/bucket/public/x.png')).toEqual({ src: 'https://cdn.example.org/bucket/public/x.png' });
    });

    it('never puts images.unsplash.com in a theme background', () => {
        const style = themeBackgroundStyle({ accent: '#FFFFFF', background: { type: 'image', imageUrl: 'https://images.unsplash.com/photo-1?ixid=x' } });
        expect(String(style.backgroundImage)).not.toContain('images.unsplash.com');
        expect(String(style.backgroundImage)).toContain(`${unsplashRouteBase()}photo-1`);
    });
});
