'use client';
import { useId } from 'react';

import Image from 'next/image';

import { ImageIcon } from 'lucide-react';

import { useDialogModal } from '@app/lib/hooks/use-dialog-modal';
import { StandardFormFieldDto } from '@app/models/dtos/form';
import { useFieldActions } from '@app/store/jotai/entity-hooks';
import { firstPartyImageProps } from '@app/utils/first-party-image';
import QuestionWrapper from '@app/views/molecules/responder-form-fields/question-wrapper';

/** The image's description for screen readers ('' marks it decorative). */
export function imageAltText(field: StandardFormFieldDto): string {
    return (field?.attachment?.properties?.description ?? '').trim();
}

/** Builder: pick the picture, describe it, or change it. */
function ImageFieldEditor({ field, slide }: { field: StandardFormFieldDto; slide: StandardFormFieldDto }) {
    const { updateFieldAttachment } = useFieldActions();
    const { openDialogModal } = useDialogModal();
    const altId = useId();
    const href: string = field?.attachment?.href ?? '';
    const alt = field?.attachment?.properties?.description ?? '';

    const save = (next: { href?: string; description?: string }) =>
        updateFieldAttachment(field.id, {
            ...(field.attachment ?? {}),
            type: 'image',
            href: next.href ?? href,
            properties: { ...(field.attachment?.properties ?? {}), description: next.description ?? alt }
        });
    const pick = () => openDialogModal('UNSPLASH_IMAGE_PICKER', { updatePageImage: (url: string) => save({ href: url }) });

    if (!href) {
        return (
            <button
                type="button"
                onClick={pick}
                className="flex h-40 w-full flex-col items-center justify-center gap-2 rounded border border-dashed border-black-400 bg-white/60 text-sm font-medium text-black-700 hover:border-black-600 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#123FC9]"
            >
                <ImageIcon className="h-6 w-6" aria-hidden="true" />
                Choose an image
            </button>
        );
    }
    return (
        <div className="flex w-full flex-col gap-2">
            <div className="relative h-40 w-full">
                <Image style={{ objectFit: 'cover' }} fill {...firstPartyImageProps(href)} alt={imageAltText(field)} />
            </div>
            <div className="flex items-end gap-2">
                <div className="flex min-w-0 flex-1 flex-col gap-1">
                    <label htmlFor={altId} className="text-xs font-medium text-black-700">
                        Description for screen readers
                    </label>
                    <input
                        id={altId}
                        type="text"
                        value={alt}
                        maxLength={250}
                        placeholder="What the image shows (leave empty if it is decoration)"
                        onChange={(event) => save({ description: event.target.value })}
                        className="rounded border border-black-300 bg-white px-2 py-1.5 text-sm text-black-900"
                    />
                </div>
                <button type="button" onClick={pick} className="rounded border border-black-400 bg-white px-3 py-1.5 text-sm font-medium text-black-800 hover:bg-black-100">
                    Change image
                </button>
            </div>
        </div>
    );
}

const ImageField = ({ field, slide, isBuilder = false }: { field: StandardFormFieldDto; slide?: StandardFormFieldDto; isBuilder?: boolean }) => {
    if (isBuilder && slide) return <ImageFieldEditor field={field} slide={slide} />;
    const href = field?.attachment?.href;
    const image = href ? (
        <div className="relative h-40 w-full">
            <Image style={{ objectFit: 'cover' }} fill {...firstPartyImageProps(href)} alt={imageAltText(field)} />
        </div>
    ) : null;
    return isBuilder ? image : <QuestionWrapper field={field}>{image}</QuestionWrapper>;
};

export default ImageField;
