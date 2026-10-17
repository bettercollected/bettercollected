'use client';

import { useId, useState } from 'react';

import { StandardFormFieldDto } from '@app/models/dtos/form';
import useFormFieldsAtom from '@app/store/jotai/field-selectors';
import QuestionWrapper from '@app/views/molecules/responder-form-fields/question-wrapper';

/**
 * Build a safe iframe src from the stored video href.
 *
 * The old construction ('https://' + href.replace('watch', 'embed')) broke in
 * two ways: an href that already carried a scheme became "https://https://…",
 * and the naive watch→embed replace corrupted any non-YouTube URL containing
 * the word "watch" (and produced youtube.com/embed?v=… — not a playable embed
 * URL — for YouTube itself).
 */
export function toEmbedUrl(href?: string): string {
    if (!href) return '';
    const withScheme = /^https?:\/\//i.test(href) ? href : `https://${href}`;
    try {
        const url = new URL(withScheme);
        const host = url.hostname.replace(/^www\.|^m\./, '');
        if (host === 'youtube.com') {
            const id = url.searchParams.get('v');
            if (id) return `https://www.youtube.com/embed/${id}`;
        }
        if (host === 'youtu.be') {
            const id = url.pathname.split('/').filter(Boolean)[0];
            if (id) return `https://www.youtube.com/embed/${id}`;
        }
        if (host === 'vimeo.com') {
            const id = url.pathname.split('/').filter(Boolean)[0];
            if (id && /^\d+$/.test(id)) return `https://player.vimeo.com/video/${id}`;
        }
        return url.toString();
    } catch {
        return withScheme;
    }
}

/** Whether a link is a YouTube or Vimeo video the form can show. */
export function isSupportedVideoUrl(href: string): boolean {
    const embed = toEmbedUrl(href.trim());
    return /^https:\/\/(www\.youtube\.com\/embed\/[\w-]+|player\.vimeo\.com\/video\/\d+)/.test(embed);
}

/** The iframe's name for screen readers: the creator's description, else a generic one. */
function videoTitle(field: StandardFormFieldDto) {
    return (field?.attachment?.properties?.description ?? '').trim() || 'Video';
}

/** Builder: paste the video's link; the player shows once it is a YouTube or Vimeo link. */
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
            {href && isSupportedVideoUrl(href) && <iframe src={toEmbedUrl(href)} title={videoTitle(field)} width="100%" className="aspect-video" allowFullScreen />}
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
    const videoUrl = toEmbedUrl(field.attachment?.href);
    const player = videoUrl ? <iframe src={videoUrl} title={videoTitle(field)} width="100%" className="aspect-video" allowFullScreen /> : null;
    return isBuilder ? player : <QuestionWrapper field={field}>{player}</QuestionWrapper>;
};

export default VideoField;
