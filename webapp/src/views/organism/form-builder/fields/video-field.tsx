'use client';

import { useId, useRef, useState } from 'react';

import { Play } from 'lucide-react';

import useRespondentLanguage from '@app/lib/hooks/use-respondent-language';
import { StandardFormFieldDto } from '@app/models/dtos/form';
import useFormFieldsAtom from '@app/store/jotai/field-selectors';
import QuestionWrapper from '@app/views/molecules/responder-form-fields/question-wrapper';

export type VideoProvider = 'YouTube' | 'Vimeo';

export interface ParsedVideo {
    provider: VideoProvider;
    id: string;
}

const YOUTUBE_ID = /^[\w-]{6,20}$/;

/**
 * The YouTube or Vimeo video a stored link points at, or null for any other
 * link. Accepts links with or without a scheme: watch, youtu.be, shorts and
 * embed links for YouTube (also youtube-nocookie.com), vimeo.com/<id> and
 * player.vimeo.com/video/<id> for Vimeo.
 */
export function parseVideoUrl(href?: string | null): ParsedVideo | null {
    const raw = (href ?? '').trim();
    if (!raw) return null;
    let url: URL;
    try {
        url = new URL(/^https?:\/\//i.test(raw) ? raw : `https://${raw}`);
    } catch {
        return null;
    }
    const host = url.hostname.toLowerCase().replace(/^(www\.|m\.)/, '');
    const parts = url.pathname.split('/').filter(Boolean);
    if (host === 'youtube.com' || host === 'youtube-nocookie.com') {
        const id = url.searchParams.get('v') ?? (['embed', 'shorts', 'live'].includes(parts[0]) ? parts[1] : undefined);
        return id && YOUTUBE_ID.test(id) ? { provider: 'YouTube', id } : null;
    }
    if (host === 'youtu.be') return parts[0] && YOUTUBE_ID.test(parts[0]) ? { provider: 'YouTube', id: parts[0] } : null;
    if (host === 'vimeo.com') return parts[0] && /^\d+$/.test(parts[0]) ? { provider: 'Vimeo', id: parts[0] } : null;
    if (host === 'player.vimeo.com' && parts[0] === 'video' && /^\d+$/.test(parts[1] ?? '')) return { provider: 'Vimeo', id: parts[1] };
    return null;
}

/**
 * The player address, loaded only once the respondent presses play (so it
 * starts playing): YouTube's no-cookie domain, Vimeo with Do Not Track.
 */
export function videoEmbedUrl(video: ParsedVideo): string {
    return video.provider === 'YouTube' ? `https://www.youtube-nocookie.com/embed/${video.id}?autoplay=1` : `https://player.vimeo.com/video/${video.id}?dnt=1&autoplay=1`;
}

/** Whether a link is a YouTube or Vimeo video the form can show. */
export function isSupportedVideoUrl(href: string): boolean {
    return parseVideoUrl(href) !== null;
}

/** What the video is called: the creator's description, else the question's title text. */
function videoTitle(field: StandardFormFieldDto): string {
    const description = (field?.attachment?.properties?.description ?? '').trim();
    if (description) return description;
    const walk = (node: any): string => (!node ? '' : node.type === 'text' ? (node.text ?? '') : (node.content ?? []).map(walk).join(' '));
    const title = typeof field?.title === 'string' ? field.title : walk(field?.title);
    return title.split(/\s+/).filter(Boolean).join(' ');
}

/**
 * Click to play. Nothing is fetched from YouTube or Vimeo until the
 * respondent presses play: before that the page shows a plain frame of our
 * own (no third-party thumbnail) that says where the video plays from and
 * that playing it shares their IP address with that site. Used on the
 * respondent page, in the preview and on the builder canvas alike.
 */
export function VideoPlayer({ field }: { field: StandardFormFieldDto }) {
    const { t } = useRespondentLanguage();
    const [playing, setPlaying] = useState(false);
    const frameRef = useRef<HTMLIFrameElement>(null);
    const noticeId = useId();
    const href = field?.attachment?.href;
    const video = parseVideoUrl(href);
    const title = videoTitle(field);

    if (!href) return null;
    if (!video) {
        // Not a provider we know how to embed privately: link out instead.
        return (
            <div className="flex aspect-video w-full flex-col items-center justify-center gap-2 rounded border border-black-300 bg-black-100 p-4 text-center text-sm text-black-800">
                <p>{t('VIDEO.UNSUPPORTED')}</p>
                <a href={/^https?:\/\//i.test(href) ? href : `https://${href}`} target="_blank" rel="noopener noreferrer nofollow" className="font-medium underline">
                    {t('VIDEO.OPEN')}
                </a>
            </div>
        );
    }
    if (playing) {
        return (
            <iframe
                ref={frameRef}
                src={videoEmbedUrl(video)}
                title={t('VIDEO.PLAYER', { title: title || video.provider })}
                width="100%"
                className="aspect-video"
                allow="autoplay; fullscreen; picture-in-picture"
                allowFullScreen
                referrerPolicy="strict-origin-when-cross-origin"
                // Keyboard and screen-reader users land in the player they asked for.
                onLoad={() => frameRef.current?.focus()}
            />
        );
    }
    return (
        <div className="flex aspect-video w-full flex-col items-center justify-center gap-3 rounded border border-black-300 bg-[#1D2433] p-4 text-center text-white">
            <button
                type="button"
                aria-describedby={noticeId}
                onClick={(event) => {
                    event.stopPropagation();
                    setPlaying(true);
                }}
                className="flex flex-col items-center gap-2 rounded px-3 py-2 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white"
            >
                <span aria-hidden="true" className="flex h-14 w-14 items-center justify-center rounded-full bg-white text-[#1D2433]">
                    <Play className="ml-1 h-6 w-6" fill="currentColor" />
                </span>
                <span className="text-base font-semibold">{title ? t('VIDEO.PLAY', { title }) : t('VIDEO.PLAY_UNTITLED')}</span>
            </button>
            <p id={noticeId} className="max-w-[46ch] text-xs opacity-80">
                {t('VIDEO.NOTICE', { provider: video.provider })}
            </p>
        </div>
    );
}

/** Builder: paste the video's link; the canvas shows the respondent's click-to-play frame. */
function VideoFieldEditor({ field, slide }: { field: StandardFormFieldDto; slide: StandardFormFieldDto }) {
    const { updateFieldAttachment } = useFormFieldsAtom();
    const inputId = useId();
    const errorId = useId();
    const href: string = field?.attachment?.href ?? '';
    const [draft, setDraft] = useState(href);
    const invalid = draft.trim() !== '' && !isSupportedVideoUrl(draft);

    const commit = () => {
        const next = draft.trim();
        if (next === href || (next && !isSupportedVideoUrl(next))) return;
        updateFieldAttachment(slide.index, field.index, { ...(field.attachment ?? {}), type: 'video', href: next });
    };

    return (
        <div className="flex w-full flex-col gap-2">
            {href && <VideoPlayer key={href} field={field} />}
            <label htmlFor={inputId} className="text-xs font-medium text-black-700">
                YouTube or Vimeo link
            </label>
            <input
                id={inputId}
                type="url"
                inputMode="url"
                value={draft}
                placeholder="https://www.youtube.com/watch?v=…"
                aria-invalid={invalid || undefined}
                aria-describedby={invalid ? errorId : undefined}
                onChange={(event) => setDraft(event.target.value)}
                onBlur={commit}
                onKeyDown={(event) => {
                    if (event.key === 'Enter') commit();
                }}
                className="rounded border border-black-300 bg-white px-2 py-1.5 text-sm text-black-900"
            />
            {invalid && (
                <p id={errorId} className="text-xs text-[#C43D3D]">
                    Paste a link to a YouTube or Vimeo video.
                </p>
            )}
        </div>
    );
}

const VideoField = ({ field, slide, isBuilder = false }: { field: StandardFormFieldDto; slide?: StandardFormFieldDto; isBuilder?: boolean }) => {
    if (isBuilder && slide) return <VideoFieldEditor field={field} slide={slide} />;
    const player = <VideoPlayer field={field} />;
    return isBuilder ? player : <QuestionWrapper field={field}>{player}</QuestionWrapper>;
};

export default VideoField;
