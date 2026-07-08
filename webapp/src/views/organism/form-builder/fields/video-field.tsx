'use client';

import { StandardFormFieldDto } from '@app/models/dtos/form';
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

const VideoField = ({ field, isBuilder = false }: { field: StandardFormFieldDto; isBuilder?: boolean }) => {
    const videoUrl = toEmbedUrl(field.attachment?.href);
    return isBuilder ? (
        <iframe src={videoUrl} width="100%" className="aspect-video"></iframe>
    ) : (
        <QuestionWrapper field={field}>
            <iframe src={videoUrl} width="100%" className="aspect-video"></iframe>
        </QuestionWrapper>
    );
};

export default VideoField;
