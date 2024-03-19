'use client';

import React, { useState } from 'react';

import Image from 'next/image';

import { useDialogModal } from '@app/lib/hooks/useDialogModal';
import { FormField } from '@app/models/dtos/form';
import { FormSlideLayout } from '@app/models/enums/form';
import { Button } from '@app/shadcn/components/ui/button';
import { cn } from '@app/shadcn/util/lib';
import useFormFieldsAtom from '@app/store/jotai/fieldSelector';
import { useFormState } from '@app/store/jotai/form';

interface ISlideLayoutWrapperProps {
    slide: FormField;
    children: React.ReactNode | React.ReactNode[];
    disabled?: boolean;
}

export default function SlideLayoutWrapper({
    slide,
    children,
    disabled = false
}: ISlideLayoutWrapperProps) {
    const [showControls, setShowControls] = useState(false);
    const { openDialogModal } = useDialogModal();

    const { activeSlide, updateSlideImage } = useFormFieldsAtom();
    const { theme } = useFormState();

    const handleGridClick = () => {
        setShowControls(!showControls);
    };

    const handleRemoveImage = () => {
        updateSlideImage('');
    };

    const handleChangeImage = () => {
        openDialogModal('UNSPLASH_IMAGE_PICKER', {
            activeSlide,
            updateSlideImage
        });
    };

    const DisplayImageWithControls = ({ imageUrl }: { imageUrl: string }) => (
        <>
            <Image
                objectFit="cover"
                className={cn(
                    'h-full w-full',
                    slide?.properties?.layout === FormSlideLayout.TWO_COLUMN_IMAGE_LEFT
                        ? 'order-0'
                        : slide?.properties?.layout ===
                            FormSlideLayout.TWO_COLUMN_IMAGE_RIGHT
                          ? 'order-1'
                          : '',
                    slide?.properties?.layout ===
                        FormSlideLayout.SINGLE_COLUMN_IMAGE_BACKGROUND
                        ? 'absolute inset-0 opacity-50 backdrop-blur-lg'
                        : 'opacity-100'
                )}
                src={imageUrl}
                alt={slide.id + ' image'}
                layout="fill"
            />

            {showControls && !disabled && (
                <div
                    className={cn(
                        'absolute flex h-full w-full items-center gap-4',
                        slide?.properties?.layout ===
                            FormSlideLayout.SINGLE_COLUMN_IMAGE_BACKGROUND
                            ? '-top-[55%] left-0'
                            : 'justify-center'
                    )}
                >
                    <Button variant="dangerGhost" onClick={handleRemoveImage}>
                        Remove
                    </Button>
                    <Button variant="secondary" onClick={handleChangeImage}>
                        Change
                    </Button>
                </div>
            )}
        </>
    );

    return (
        <>
            <div
                style={{
                    backgroundColor: slide?.properties?.theme?.accent || theme?.accent
                }}
                className={cn(
                    'relative grid aspect-video h-min w-full overflow-hidden rounded-lg bg-white',
                    slide?.properties?.layout ===
                        FormSlideLayout.TWO_COLUMN_IMAGE_LEFT ||
                        slide?.properties?.layout ===
                            FormSlideLayout.TWO_COLUMN_IMAGE_RIGHT
                        ? 'grid-cols-2'
                        : 'grid-cols-1',
                    disabled ? 'pointer-events-none overflow-hidden' : ''
                )}
            >
                {children}

                {/* Image with controls works for left and right image layout */}
                {slide?.properties?.layout !==
                    FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND &&
                    slide?.properties?.layout !==
                        FormSlideLayout.SINGLE_COLUMN_IMAGE_BACKGROUND && (
                        <div
                            className={cn(
                                'relative',
                                slide?.properties?.layout ===
                                    FormSlideLayout.TWO_COLUMN_IMAGE_LEFT ||
                                    slide?.properties?.layout ===
                                        FormSlideLayout.TWO_COLUMN_IMAGE_RIGHT
                                    ? 'grid-cols-1'
                                    : '',
                                slide?.imageUrl
                                    ? 'hover:cursor-pointer hover:!bg-black/30'
                                    : 'bg-neutral-100 shadow hover:cursor-default'
                            )}
                            onClick={handleGridClick}
                            role="button"
                        >
                            {slide?.imageUrl ? (
                                <DisplayImageWithControls imageUrl={slide.imageUrl} />
                            ) : (
                                <div
                                    className={cn(
                                        'flex h-full items-center justify-center text-lg font-semibold'
                                    )}
                                >
                                    <Button
                                        variant="secondary"
                                        onClick={handleChangeImage}
                                    >
                                        Select Layout Image
                                    </Button>
                                </div>
                            )}
                        </div>
                    )}
            </div>

            {/* Layout logic for background image or no background image */}
            {slide?.properties?.layout ===
                FormSlideLayout.SINGLE_COLUMN_IMAGE_BACKGROUND && (
                <div
                    className={cn(
                        'relative z-0',
                        slide?.imageUrl
                            ? 'hover:cursor-pointer hover:!bg-black/30'
                            : 'bg-neutral-100 shadow hover:cursor-default',
                        slide?.properties?.layout ===
                            FormSlideLayout.SINGLE_COLUMN_IMAGE_BACKGROUND
                            ? 'absolute inset-0 top-1/2 aspect-video h-min -translate-y-1/2 transform !bg-transparent'
                            : ''
                    )}
                    onClick={handleGridClick}
                    role="button"
                >
                    {/* No need to show controls for single column without background layout */}
                    {slide?.imageUrl &&
                    slide?.properties?.layout ===
                        FormSlideLayout.SINGLE_COLUMN_IMAGE_BACKGROUND ? (
                        <DisplayImageWithControls imageUrl={slide.imageUrl} />
                    ) : (
                        <div
                            className={cn(
                                'flex h-full items-center justify-center text-lg font-semibold',
                                slide?.properties?.layout ===
                                    FormSlideLayout.SINGLE_COLUMN_IMAGE_BACKGROUND
                                    ? 'absolute -top-[55%] left-0'
                                    : ''
                            )}
                        >
                            <Button variant="secondary" onClick={handleChangeImage}>
                                Select Layout Image
                            </Button>
                        </div>
                    )}
                </div>
            )}
        </>
    );
}
