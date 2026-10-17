import React from 'react';

import { act, fireEvent, render, screen } from '@testing-library/react';
import { Provider as ReduxProvider } from 'react-redux';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const importImageMock = vi.fn();
vi.mock('@app/store/media-library/api', async (importOriginal) => {
    const actual: any = await importOriginal();
    return { ...actual, useImportImageFromUrlMutation: () => [importImageMock, { isLoading: false }] };
});

import { store } from '@app/store/store';
import { setWorkspace } from '@app/store/workspaces/slice';
import ImageUrlField, { COPY_FAILED_MESSAGE, importErrorMessage } from './image-url-field';

const OURS = 'https://cdn.example.org/bucket/public/media/ws1/abc.jpg';

const renderField = (value = '', onChange = vi.fn()) => {
    render(
        <ReduxProvider store={store}>
            <ImageUrlField value={value} onChange={onChange} />
        </ReduxProvider>
    );
    return onChange;
};

const paste = async (url: string) => {
    fireEvent.change(screen.getByLabelText('Background image URL'), { target: { value: url } });
    await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: 'Use image' }));
    });
};

describe('ImageUrlField (a pasted background image is copied in first)', () => {
    beforeEach(() => {
        importImageMock.mockReset();
        store.dispatch(setWorkspace({ id: 'ws1' } as any));
    });

    it('copies the address and stores our address for it, not the pasted one', async () => {
        importImageMock.mockResolvedValue({ data: { url: OURS } });
        const onChange = renderField();
        await paste('https://photos.example.org/cat.jpg');
        expect(importImageMock).toHaveBeenCalledWith({ workspace_id: 'ws1', url: 'https://photos.example.org/cat.jpg' });
        expect(onChange).toHaveBeenCalledWith(OURS);
        expect(onChange).not.toHaveBeenCalledWith('https://photos.example.org/cat.jpg');
    });

    it("says plainly when the image couldn't be copied, and keeps the old image", async () => {
        importImageMock.mockResolvedValue({ error: { status: 422, data: { code: 'not_image', message: "We couldn't copy that image. It isn't a JPEG, PNG or WebP image. Upload it instead." } } });
        const onChange = renderField(OURS);
        await paste('https://photos.example.org/page.html');
        expect(screen.getByRole('alert').textContent).toContain("We couldn't copy that image.");
        expect(screen.getByRole('alert').textContent).toContain('Upload it instead.');
        expect(onChange).not.toHaveBeenCalled();
    });

    it('falls back to the general message', () => {
        expect(importErrorMessage({ status: 503 })).toBe(COPY_FAILED_MESSAGE);
        expect(importErrorMessage(undefined)).toBe(COPY_FAILED_MESSAGE);
        expect(COPY_FAILED_MESSAGE).toBe("We couldn't copy that image. Upload it instead.");
    });

    it('copies nothing while the address is unchanged, and clears the image when emptied', async () => {
        const onChange = renderField(OURS);
        expect((screen.getByRole('button', { name: 'Use image' }) as HTMLButtonElement).disabled).toBe(true);
        await paste('');
        expect(importImageMock).not.toHaveBeenCalled();
        expect(onChange).toHaveBeenCalledWith('');
    });
});
