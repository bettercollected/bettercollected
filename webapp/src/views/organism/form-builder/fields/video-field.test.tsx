import React from 'react';

import { act, fireEvent, render, screen } from '@testing-library/react';
import { Provider } from 'jotai';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
// Registers the respondent translations, as the app layout does.
import '@app/shared/hocs/i18n-provider';

import en from '../../../../../public/locales/en/respondent.json';
import nl from '../../../../../public/locales/nl/respondent.json';
import VideoField, { VideoPlayer, isSupportedVideoUrl, parseVideoUrl, videoEmbedUrl } from './video-field';

const video = (href: string, description?: string): StandardFormFieldDto => ({
    id: 'v1',
    index: 0,
    type: FieldTypes.VIDEO_CONTENT,
    attachment: { type: 'video', href, properties: description ? { description } : {} }
});

const renderPlayer = (field: StandardFormFieldDto) =>
    render(
        <Provider>
            <VideoPlayer field={field} />
        </Provider>
    );

afterEach(() => window.history.replaceState(null, '', '/'));

describe('parseVideoUrl / videoEmbedUrl', () => {
    it('reads YouTube links in their usual shapes, with or without a scheme', () => {
        for (const href of [
            'www.youtube.com/watch?v=abc123XYZ',
            'https://youtu.be/abc123XYZ',
            'https://www.youtube.com/shorts/abc123XYZ',
            'https://www.youtube.com/embed/abc123XYZ',
            'https://www.youtube-nocookie.com/embed/abc123XYZ',
            'https://m.youtube.com/watch?v=abc123XYZ'
        ]) {
            expect(parseVideoUrl(href)).toEqual({ provider: 'YouTube', id: 'abc123XYZ' });
        }
    });

    it('reads Vimeo links', () => {
        expect(parseVideoUrl('https://vimeo.com/12345678')).toEqual({ provider: 'Vimeo', id: '12345678' });
        expect(parseVideoUrl('https://player.vimeo.com/video/12345678')).toEqual({ provider: 'Vimeo', id: '12345678' });
    });

    it('rejects anything else, including look-alike hosts', () => {
        for (const href of ['', 'https://example.com/watchtower/video.mp4', 'https://youtube.com.evil.example/watch?v=abc123XYZ', 'https://vimeo.com/channels/staff', 'javascript:alert(1)']) {
            expect(parseVideoUrl(href)).toBeNull();
            expect(isSupportedVideoUrl(href)).toBe(false);
        }
    });

    it('plays YouTube from the no-cookie domain and Vimeo with Do Not Track', () => {
        expect(videoEmbedUrl({ provider: 'YouTube', id: 'abc123XYZ' })).toBe('https://www.youtube-nocookie.com/embed/abc123XYZ?autoplay=1');
        expect(videoEmbedUrl({ provider: 'Vimeo', id: '12345678' })).toBe('https://player.vimeo.com/video/12345678?dnt=1&autoplay=1');
    });
});

describe('VideoPlayer: click to play', () => {
    it('loads nothing from YouTube until the play button is pressed', async () => {
        const { container } = renderPlayer(video('https://www.youtube.com/watch?v=abc123XYZ', 'How to apply'));
        expect(container.querySelector('iframe')).toBeNull();
        expect(container.querySelector('img')).toBeNull();
        // nothing that loads anything: no src, srcset, href or background image
        expect(container.querySelectorAll('[src], [srcset], [href], [style*="url("]')).toHaveLength(0);

        const play = screen.getByRole('button', { name: 'Play video: How to apply' });
        expect(play).toHaveAccessibleDescription('Plays from YouTube. Playing it shares your IP address with YouTube.');
        play.focus();
        expect(play).toHaveFocus();
        await act(async () => fireEvent.click(play));

        const frame = container.querySelector('iframe')!;
        expect(frame.getAttribute('src')).toBe('https://www.youtube-nocookie.com/embed/abc123XYZ?autoplay=1');
        expect(frame).toHaveAttribute('title', 'Video player: How to apply');
        const focus = vi.spyOn(frame, 'focus');
        fireEvent.load(frame);
        expect(focus).toHaveBeenCalled();
    });

    it('plays Vimeo with Do Not Track after the click', async () => {
        const { container } = renderPlayer(video('https://vimeo.com/12345678'));
        expect(container.querySelector('iframe')).toBeNull();
        expect(screen.getByText('Plays from Vimeo. Playing it shares your IP address with Vimeo.')).toBeInTheDocument();
        await act(async () => fireEvent.click(screen.getByRole('button', { name: 'Play video' })));
        expect(container.querySelector('iframe')!.getAttribute('src')).toBe('https://player.vimeo.com/video/12345678?dnt=1&autoplay=1');
    });

    it('is a real button, so Enter or Space starts it like a click', () => {
        renderPlayer(video('https://youtu.be/abc123XYZ'));
        const play = screen.getByRole('button', { name: 'Play video' });
        expect(play.tagName).toBe('BUTTON');
        expect(play).toHaveAttribute('type', 'button');
        expect(play).not.toHaveAttribute('tabindex', '-1');
    });

    it('says it in Dutch for Dutch respondents', async () => {
        window.history.replaceState(null, '', '/?lang=nl');
        renderPlayer(video('https://youtu.be/abc123XYZ', 'Uitleg'));
        expect(await screen.findByRole('button', { name: 'Video afspelen: Uitleg' })).toHaveAccessibleDescription('Wordt afgespeeld via YouTube. Afspelen deelt je IP-adres met YouTube.');
    });

    it('never embeds another site: it links out instead', () => {
        const { container } = renderPlayer(video('https://example.com/clip'));
        expect(container.querySelector('iframe')).toBeNull();
        const link = screen.getByRole('link', { name: 'Open the video in a new tab' });
        expect(link).toHaveAttribute('href', 'https://example.com/clip');
        expect(link).toHaveAttribute('rel', expect.stringContaining('noopener'));
    });

    it('has the notice in both respondent languages', () => {
        expect(en.VIDEO.NOTICE).toBe('Plays from {{provider}}. Playing it shares your IP address with {{provider}}.');
        expect(nl.VIDEO.NOTICE).toBe('Wordt afgespeeld via {{provider}}. Afspelen deelt je IP-adres met {{provider}}.');
        expect(Object.keys(nl.VIDEO).sort()).toEqual(Object.keys(en.VIDEO).sort());
    });
});

describe('the builder canvas', () => {
    it('shows creators the same click-to-play frame, with no player loaded', () => {
        const field = video('https://youtu.be/abc123XYZ');
        const slide = { id: 'p', index: 0, type: FieldTypes.SLIDE, properties: { fields: [field] } } as StandardFormFieldDto;
        const { container } = render(
            <Provider>
                <VideoField isBuilder field={field} slide={slide} />
            </Provider>
        );
        expect(container.querySelector('iframe')).toBeNull();
        expect(screen.getByRole('button', { name: 'Play video' })).toBeInTheDocument();
        expect(screen.getByRole('textbox', { name: 'YouTube or Vimeo link' })).toHaveValue('https://youtu.be/abc123XYZ');
    });
});
