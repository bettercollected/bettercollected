'use client';

import { useState } from 'react';

import Image from 'next/image';

import { useDialogModal } from '@app/lib/hooks/useDialogModal';
import { FormSlideLayout } from '@app/models/enums/form';
import { Button } from '@app/shadcn/components/ui/button';
import { cn } from '@app/shadcn/util/lib';
import { useFormState } from '@app/store/jotai/form';

interface ILayoutWrapper {
    layout?: FormSlideLayout;
    imageUrl?: string;
    updatePageImage?: (...args: any[]) => void;
    altImage?: string;
    disabled?: boolean;
    style?: React.CSSProperties;
    children: React.ReactNode | React.ReactNode[];
}

const LayoutWrapper = ({
    layout,
    imageUrl,
    updatePageImage,
    altImage,
    disabled = false,
    style = {},
    children
}: ILayoutWrapper) => {
    const [showControls, setShowControls] = useState(false);
    const { openDialogModal } = useDialogModal();
    const { theme } = useFormState();

    const handleGridClick = () => {
        setShowControls(!showControls);
    };

    const handleRemoveImage = () => {
        updatePageImage && updatePageImage('');
    };

    const handleChangeImage = () => {
        openDialogModal('UNSPLASH_IMAGE_PICKER', {
            updatePageImage
        });
    };

    const DisplayImageWithControls = ({ imageUrl }: { imageUrl: string }) => (
        <>
            <Image
                objectFit="cover"
                className={cn(
                    'h-full w-full',
                    layout === FormSlideLayout.TWO_COLUMN_IMAGE_LEFT
                        ? 'order-0'
                        : layout === FormSlideLayout.TWO_COLUMN_IMAGE_RIGHT
                          ? 'order-1'
                          : '',
                    layout === FormSlideLayout.SINGLE_COLUMN_IMAGE_BACKGROUND
                        ? 'absolute inset-0 opacity-50 backdrop-blur-lg'
                        : 'opacity-100'
                )}
                src={imageUrl}
                alt={altImage + ' image'}
                layout="fill"
                priority
            />

            {(showControls ||
                layout === FormSlideLayout.SINGLE_COLUMN_IMAGE_BACKGROUND) &&
                !disabled && (
                    <div
                        className={cn(
                            'absolute flex h-full w-full items-center gap-4',
                            layout === FormSlideLayout.SINGLE_COLUMN_IMAGE_BACKGROUND
                                ? '-top-[52%] left-0'
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
                    backgroundColor: theme?.accent,
                    ...style
                }}
                className={cn(
                    'relative grid aspect-video h-min w-full overflow-hidden rounded-lg bg-white',
                    layout === FormSlideLayout.TWO_COLUMN_IMAGE_LEFT ||
                        layout === FormSlideLayout.TWO_COLUMN_IMAGE_RIGHT
                        ? 'grid-cols-2'
                        : 'grid-cols-1',
                    disabled ? 'h-full overflow-hidden' : ''
                )}
            >
                {children}

                {/* Image with controls works for left and right image layout */}
                {layout &&
                    layout !== FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND &&
                    layout !== FormSlideLayout.SINGLE_COLUMN_IMAGE_BACKGROUND && (
                        <div
                            className={cn(
                                'relative',
                                (layout &&
                                    layout === FormSlideLayout.TWO_COLUMN_IMAGE_LEFT) ||
                                    (layout &&
                                        layout ===
                                            FormSlideLayout.TWO_COLUMN_IMAGE_RIGHT)
                                    ? 'grid-cols-1'
                                    : '',
                                imageUrl && !disabled
                                    ? 'hover:cursor-pointer hover:!bg-black/30'
                                    : 'bg-neutral-100 shadow hover:cursor-default'
                            )}
                            onClick={disabled ? () => {} : handleGridClick}
                            role="button"
                            {...(disabled
                                ? { tabIndex: -1, 'aria-disabled': true }
                                : {})}
                        >
                            {imageUrl ? (
                                <DisplayImageWithControls imageUrl={imageUrl} />
                            ) : (
                                !disabled && (
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
                                )
                            )}
                        </div>
                    )}
            </div>

            {/* Layout logic for background image or no background image */}
            {layout && layout === FormSlideLayout.SINGLE_COLUMN_IMAGE_BACKGROUND && (
                <div
                    className={cn(
                        'test relative z-0',
                        imageUrl && !disabled
                            ? 'hover:cursor-pointer hover:!bg-black/30'
                            : 'bg-neutral-100 shadow hover:cursor-default',
                        layout === FormSlideLayout.SINGLE_COLUMN_IMAGE_BACKGROUND
                            ? 'absolute inset-0 top-1/2 aspect-video h-fit -translate-y-1/2 transform !bg-transparent'
                            : '',
                        disabled ? 'h-full' : ''
                    )}
                    onClick={disabled ? () => {} : handleGridClick}
                    role="button"
                    {...(disabled ? { tabIndex: -1, 'aria-disabled': true } : {})}
                >
                    {/* No need to show controls for single column without background layout */}
                    {imageUrl ? (
                        <DisplayImageWithControls imageUrl={imageUrl} />
                    ) : (
                        !disabled && (
                            <div
                                className={cn(
                                    'flex h-full items-center justify-center text-lg font-semibold',
                                    layout ===
                                        FormSlideLayout.SINGLE_COLUMN_IMAGE_BACKGROUND
                                        ? 'absolute -top-[52%] left-0'
                                        : ''
                                )}
                            >
                                <Button variant="secondary" onClick={handleChangeImage}>
                                    Select Layout Image
                                </Button>
                            </div>
                        )
                    )}
                </div>
            )}
        </>
    );
};

export default LayoutWrapper;
