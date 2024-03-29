'use client';

import { useState } from 'react';

import Image from 'next/image';

import { FormTheme } from '@app/constants/theme';
import { useDialogModal } from '@app/lib/hooks/useDialogModal';
import { FormSlideLayout } from '@app/models/enums/form';
import { Button } from '@app/shadcn/components/ui/button';
import { cn } from '@app/shadcn/util/lib';
import { useFormState } from '@app/store/jotai/form';
import DeleteIcon from '@app/views/atoms/Icons/Delete';
import { SwitchIcon } from '@app/views/atoms/Icons/SwitchIcon';

interface ILayoutWrapper {
    layout?: FormSlideLayout;
    imageUrl?: string;
    updatePageImage?: (...args: any[]) => void;
    updatePageLayout?: (...args: any[]) => void;
    altImage?: string;
    disabled?: boolean;
    theme?: FormTheme;
    style?: React.CSSProperties;
    children: React.ReactNode | React.ReactNode[];
}

const LayoutWrapper = ({
    layout,
    theme,
    imageUrl,
    updatePageImage,
    updatePageLayout,
    altImage,
    disabled = false,
    style = {},
    children
}: ILayoutWrapper) => {
    const [showControls, setShowControls] = useState(false);
    const { openDialogModal } = useDialogModal();

    const handleGridClick = () => {
        setShowControls(!showControls);
    };

    const handleRemoveImage = () => {
        updatePageImage && updatePageImage('');
        updatePageLayout &&
            updatePageLayout(FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND);
    };

    const handleChangeImage = () => {
        openDialogModal('UNSPLASH_IMAGE_PICKER', {
            updatePageImage
        });
    };

    const DisplayImageWithControls = ({ imageUrl }: { imageUrl: string }) => (
        <>
            <Image
                style={{ objectFit: 'cover' }}
                className={cn(
                    'h-full w-full',
                    layout === FormSlideLayout.TWO_COLUMN_IMAGE_LEFT
                        ? 'order-0'
                        : layout === FormSlideLayout.TWO_COLUMN_IMAGE_RIGHT
                          ? 'order-1'
                          : '',
                    layout === FormSlideLayout.SINGLE_COLUMN_IMAGE_BACKGROUND
                        ? 'opacity-50 backdrop-blur-lg'
                        : 'opacity-100'
                )}
                src={imageUrl}
                alt={altImage + ' image'}
                fill
                priority
            />

            {(showControls ||
                layout === FormSlideLayout.SINGLE_COLUMN_IMAGE_BACKGROUND) &&
                !disabled && (
                    <div
                        className={cn(
                            'absolute flex h-full w-full items-start justify-end gap-4 p-2',
                            layout === FormSlideLayout.SINGLE_COLUMN_IMAGE_BACKGROUND
                                ? '-top-[50px]'
                                : ''
                        )}
                    >
                        <div
                            className="cursor-pointer rounded-md bg-white p-2 shadow-bubble"
                            onClick={handleRemoveImage}
                        >
                            <DeleteIcon width={24} height={24} />
                        </div>
                        <div
                            className=" cursor-pointer rounded-md bg-white p-2 shadow-bubble"
                            onClick={handleChangeImage}
                        >
                            <SwitchIcon />
                        </div>
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
                    'relative flex  aspect-video h-min w-full overflow-hidden rounded-lg !bg-transparent lg:grid',
                    layout === FormSlideLayout.TWO_COLUMN_IMAGE_RIGHT
                        ? 'flex-col-reverse'
                        : 'flex-col',
                    layout === FormSlideLayout.TWO_COLUMN_IMAGE_LEFT ||
                        layout === FormSlideLayout.TWO_COLUMN_IMAGE_RIGHT
                        ? 'lg:grid-cols-2'
                        : 'lg:grid-cols-1',
                    disabled ? 'h-full overflow-hidden' : ''
                )}
            >
                <div
                    style={{
                        background: theme?.accent
                    }}
                    // TODO: Change this to apply layout from other layout
                    className={cn(
                        'relative px-5 md:px-10 xl:px-20',
                        ' grid aspect-video h-full w-full grid-cols-1',
                        disabled ? 'overflow-hidden' : '',
                        layout &&
                            layout === FormSlideLayout.SINGLE_COLUMN_IMAGE_BACKGROUND
                            ? 'z-10 !bg-transparent'
                            : '',
                        layout && layout === FormSlideLayout.TWO_COLUMN_IMAGE_LEFT
                            ? 'order-1'
                            : layout &&
                                layout === FormSlideLayout.TWO_COLUMN_IMAGE_RIGHT
                              ? 'order-0'
                              : ''
                    )}
                >
                    {children}
                </div>
                {/* Image with controls works for left and right image layout */}
                {layout &&
                    layout !== FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND &&
                    layout !== FormSlideLayout.SINGLE_COLUMN_IMAGE_BACKGROUND && (
                        <div
                            className={cn(
                                'relative h-[30%] lg:h-auto ',
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
                            // onClick={disabled ? () => {} : handleGridClick}
                            onMouseOver={
                                disabled ? () => {} : () => setShowControls(true)
                            }
                            onMouseLeave={
                                disabled ? () => {} : () => setShowControls(false)
                            }
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
                        'relative z-0',
                        imageUrl && !disabled
                            ? 'hover:cursor-pointer hover:!bg-black/30'
                            : 'bg-neutral-100 hover:cursor-default',
                        layout === FormSlideLayout.SINGLE_COLUMN_IMAGE_BACKGROUND
                            ? 'absolute inset-0 top-1/2 aspect-video -translate-y-1/2 transform '
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
