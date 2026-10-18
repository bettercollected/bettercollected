import React from 'react';

import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { Provider as ReduxProvider } from 'react-redux';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { store } from '@app/store/store';

import UnsplashImagePicker from './index';

vi.mock('./upload-media-comonent', () => ({ default: () => null, SkeletonLoadingComponent: () => <div>Loading</div> }));
vi.mock('@app/lib/hooks/use-dialog-modal', () => ({ useDialogModal: () => ({ closeDialogModal: () => {} }) }));

const PHOTO = {
    id: 'mtNweauBsMQ',
    alt_description: 'a quiet lake',
    urls: { raw: 'https://images.unsplash.com/photo-1', small: 'https://images.unsplash.com/photo-1?w=400' },
    user: { name: 'A Photographer', username: 'photographer', links: { html: 'https://unsplash.com/@photographer' }, profile_image: { small: 'https://images.unsplash.com/profile-1' } }
};

const fetchMock = vi.fn();

const openPicker = (updatePageImage = vi.fn()) => {
    render(
        <ReduxProvider store={store}>
            <UnsplashImagePicker initialPhotoSearchQuery="Minimal" updatePageImage={updatePageImage} />
        </ReduxProvider>
    );
    fireEvent.mouseDown(screen.getByRole('tab', { name: 'Images' }), { button: 0 });
    return updatePageImage;
};

const searches = () => fetchMock.mock.calls.filter(([url]) => String(url).includes('/api/unsplash?'));

describe('UnsplashImagePicker', () => {
    beforeEach(() => {
        fetchMock.mockReset();
        vi.stubGlobal('fetch', fetchMock);
    });
    afterEach(() => vi.unstubAllGlobals());

    it('shows the search results and tracks a picked photo by its id only', async () => {
        fetchMock.mockImplementation(async (url: string) =>
            String(url).includes('/download') ? new Response('{}', { status: 200 }) : new Response(JSON.stringify({ total: 1, total_pages: 1, results: [PHOTO] }), { status: 200 })
        );
        const updatePageImage = openPicker();

        fireEvent.click(await screen.findByAltText('a quiet lake'));

        expect(updatePageImage).toHaveBeenCalledWith(PHOTO.urls.raw);
        const download = fetchMock.mock.calls.find(([url]) => url === '/api/unsplash/download');
        expect(JSON.parse(download![1].body)).toEqual({ id: PHOTO.id });
        expect(screen.queryByRole('alert')).not.toBeInTheDocument();
        expect(searches().every(([url]) => new URL(url).searchParams.get('query') === 'Minimal')).toBe(true);
    });

    it('asks to sign in again when the session has ended', async () => {
        fetchMock.mockResolvedValue(new Response(JSON.stringify({ message: 'Sign in to search images.' }), { status: 401 }));
        openPicker();

        expect(await screen.findByRole('alert')).toHaveTextContent('Sign in again to search images.');
        expect(screen.queryByAltText('a quiet lake')).not.toBeInTheDocument();
    });

    it('says when there were too many searches', async () => {
        fetchMock.mockResolvedValue(new Response('{}', { status: 429, headers: { 'Retry-After': '60' } }));
        openPicker();

        expect(await screen.findByRole('alert')).toHaveTextContent('Too many image searches.');
    });

    it('says search is unavailable when the request fails, and stops loading', async () => {
        fetchMock.mockRejectedValue(new TypeError('fetch failed'));
        openPicker();

        expect(await screen.findByRole('alert')).toHaveTextContent('Image search is unavailable right now.');
        await waitFor(() => expect(screen.queryByText('Loading')).not.toBeInTheDocument());
    });
});
