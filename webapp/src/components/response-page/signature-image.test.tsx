import React from 'react';

import { render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import environments from '@app/configs/environments';

import SignatureImage, { signatureImageUrl } from './signature-image';

const PATH = '/workspaces/w1/submissions/r1/signatures/sig';
const png = (init: ResponseInit = {}) => new Response(new Blob([new Uint8Array([0x89, 0x50, 0x4e, 0x47])], { type: 'image/png' }), { status: 200, headers: { 'content-type': 'image/png' }, ...init });

const show = (url = PATH) => render(<SignatureImage url={url} alt="Drawn signature" unavailable="Image not available" />);

beforeEach(() => {
    URL.createObjectURL = vi.fn(() => 'blob:sig-1');
    URL.revokeObjectURL = vi.fn();
});

afterEach(() => {
    vi.unstubAllGlobals();
});

describe('a drawn signature image', () => {
    it('only builds the address of an API path, never of another address', () => {
        expect(signatureImageUrl(PATH)).toBe(`${environments.API_ENDPOINT_HOST}${PATH}`);
        for (const other of ['https://evil.example/x.png', '//evil.example/x.png', 'javascript:alert(1)', 'data:image/png;base64,AAAA', '', undefined]) {
            expect(signatureImageUrl(other as any)).toBeNull();
        }
    });

    it('fetches the decrypted image with credentials, uncached and without a referrer, and shows it from a blob address', async () => {
        const fetchMock = vi.fn(async () => png());
        vi.stubGlobal('fetch', fetchMock);
        show();
        const image = await screen.findByRole('img', { name: 'Drawn signature' });
        expect(image).toHaveAttribute('src', 'blob:sig-1');
        expect(image).toHaveAttribute('referrerpolicy', 'no-referrer');
        expect(fetchMock).toHaveBeenCalledTimes(1);
        const [target, options] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
        expect(target).toBe(`${environments.API_ENDPOINT_HOST}${PATH}`);
        expect(options).toMatchObject({ credentials: 'include', cache: 'no-store', referrerPolicy: 'no-referrer' });
    });

    it('revokes the blob address when the view goes away', async () => {
        vi.stubGlobal(
            'fetch',
            vi.fn(async () => png())
        );
        const { unmount } = show();
        await screen.findByRole('img');
        unmount();
        expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:sig-1');
    });

    it('does not fetch an address that is not an API path, and says the image is not available', async () => {
        const fetchMock = vi.fn(async () => png());
        vi.stubGlobal('fetch', fetchMock);
        show('https://files.example/private/x?signed');
        expect(await screen.findByText('Image not available')).toBeInTheDocument();
        expect(fetchMock).not.toHaveBeenCalled();
    });

    it.each([
        ['a refusal', () => new Response('nope', { status: 404 })],
        ['something that is not a PNG', () => new Response('<svg/>', { status: 200, headers: { 'content-type': 'image/svg+xml' } })]
    ])('says the image is not available for %s', async (_name, reply) => {
        vi.stubGlobal(
            'fetch',
            vi.fn(async () => reply())
        );
        show();
        expect(await screen.findByText('Image not available')).toBeInTheDocument();
        expect(screen.queryByRole('img')).toBeNull();
        expect(URL.createObjectURL).not.toHaveBeenCalled();
    });

    it('says the image is not available when the request fails', async () => {
        vi.stubGlobal(
            'fetch',
            vi.fn(async () => Promise.reject(new TypeError('network')))
        );
        show();
        await waitFor(() => expect(screen.getByText('Image not available')).toBeInTheDocument());
    });
});
