'use client';

import { useState } from 'react';

import Image from 'next/image';

import { FormTheme } from '@app/constants/theme';
import { useDialogModal } from '@app/lib/hooks/useDialogModal';
import { FormSlideLayout } from '@app/models/enums/form';
import { Button } from '@app/shadcn/components/ui/button';
import { ScrollArea } from '@app/shadcn/components/ui/scroll-area';
import { cn } from '@app/shadcn/util/lib';
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
    scrollDivId?: string;
    children: React.ReactNode | React.ReactNode[];
    showDesktopLayout?: boolean;
}

const LayoutWrapper = ({ layout, theme, imageUrl, updatePageImage, updatePageLayout, altImage, disabled = false, style = {}, scrollDivId, children, showDesktopLayout = false }: ILayoutWrapper) => {
    const [showControls, setShowControls] = useState(false);
    const { openDialogModal } = useDialogModal();

    const handleGridClick = () => {
        setShowControls(!showControls);
    };

    const handleRemoveImage = () => {
        updatePageImage && updatePageImage('');
        updatePageLayout && updatePageLayout(FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND);
    };

    const handleChangeImage = () => {
        openDialogModal('UNSPLASH_IMAGE_PICKER', {
            updatePageImage
        });
    };
    const DisplayImageWithControls = ({ imageUrl }: { imageUrl: string }) => {
        return (
            <>
                <Image
                    style={{ objectFit: 'cover' }}
                    className={cn(
                        'h-full w-full',
                        layout === FormSlideLayout.TWO_COLUMN_IMAGE_LEFT ? 'order-0' : layout === FormSlideLayout.TWO_COLUMN_IMAGE_RIGHT ? 'order-1' : '',
                        layout === FormSlideLayout.SINGLE_COLUMN_IMAGE_BACKGROUND ? 'rounded-lg opacity-50 backdrop-blur-lg' : 'opacity-100'
                    )}
                    src={imageUrl}
                    alt={altImage + ' image'}
                    loader={
                        imageUrl.includes('images.unsplash.com')
                            ? ({ src, width, quality }) => {
                                  return src + `&q=${quality || '0.5'}&w=${width}&cs=tinysrgb&auto=format&dpr=1`;
                              }
                            : undefined
                    }
                    fill
                    priority
                />

                {(showControls || layout === FormSlideLayout.SINGLE_COLUMN_IMAGE_BACKGROUND) && !disabled && (
                    <div className={cn('absolute flex h-full w-full items-start justify-end gap-4 p-2', layout === FormSlideLayout.SINGLE_COLUMN_IMAGE_BACKGROUND ? '' : '')}>
                        <div className="shadow-bubble z-10 cursor-pointer rounded-md bg-white p-2" onClick={handleRemoveImage}>
                            <DeleteIcon width={24} height={24} />
                        </div>
                        <div className=" shadow-bubble z-10 cursor-pointer rounded-md bg-white p-2" onClick={handleChangeImage}>
                            <SwitchIcon />
                        </div>
                    </div>
                )}
            </>
        );
    };
    return (
        <>
            <div
                style={{
                    backgroundColor: theme?.accent,
                    ...style
                }}
                className={cn(
                    showDesktopLayout ? 'grid' : 'flex lg:grid',
                    'relative  h-full w-full flex-grow overflow-hidden !bg-transparent lg:rounded-lg',
                    layout === FormSlideLayout.TWO_COLUMN_IMAGE_RIGHT ? 'flex-col-reverse justify-end' : 'flex-col justify-end',
                    layout === FormSlideLayout.TWO_COLUMN_IMAGE_LEFT || layout === FormSlideLayout.TWO_COLUMN_IMAGE_RIGHT ? 'grid-cols-2' : 'grid-cols-1',
                    disabled ? 'h-full overflow-hidden' : ''
                )}
            >
                <ScrollArea
                    thumbBg={theme?.tertiary}
                    id={scrollDivId}
                    asChild
                    style={{
                        background: layout === FormSlideLayout.SINGLE_COLUMN_IMAGE_BACKGROUND ? 'transparent' : theme?.accent
                    }}
                    // TODO: Change this to apply layout from other layout
                    className={cn(
                        'relative px-5 md:px-8 xl:px-10 2xl:px-20',
                        'flex-grow lg:min-h-[100%]',
                        disabled ? 'overflow-hidden' : '',
                        layout && layout === FormSlideLayout.SINGLE_COLUMN_IMAGE_BACKGROUND ? 'z-10 !bg-transparent' : '',
                        layout && layout === FormSlideLayout.TWO_COLUMN_IMAGE_LEFT ? 'order-1' : layout && layout === FormSlideLayout.TWO_COLUMN_IMAGE_RIGHT ? 'order-0' : ''
                    )}
                >
                    <div className="flex min-h-[100%] w-full flex-col justify-center py-[60px]">{children}</div>
                </ScrollArea>
                {/* Image with controls works for left and right image layout */}
                {layout && layout !== FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND && layout !== FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND_LEFT_ALIGN && layout !== FormSlideLayout.SINGLE_COLUMN_IMAGE_BACKGROUND && (
                    <div
                        className={cn(
                            'relative',
                            showDesktopLayout ? 'h-auto ' : ' h-[30%] lg:h-auto',
                            (layout && layout === FormSlideLayout.TWO_COLUMN_IMAGE_LEFT) || (layout && layout === FormSlideLayout.TWO_COLUMN_IMAGE_RIGHT) ? 'grid-cols-1' : '',
                            imageUrl && !disabled ? 'hover:cursor-pointer hover:!bg-black/30' : 'bg-neutral-100 shadow hover:cursor-default'
                        )}
                        // onClick={disabled ? () => {} : handleGridClick}
                        onMouseOver={disabled ? () => {} : () => setShowControls(true)}
                        onMouseLeave={disabled ? () => {} : () => setShowControls(false)}
                        {...(disabled ? { tabIndex: -1, 'aria-disabled': true } : {})}
                    >
                        {imageUrl ? (
                            <DisplayImageWithControls imageUrl={imageUrl} />
                        ) : (
                            !disabled && (
                                <div className={cn('flex h-full items-center justify-center text-lg font-semibold')}>
                                    <Button variant="secondary" onClick={handleChangeImage}>
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
                        'relative',
                        imageUrl && !disabled ? 'hover:cursor-pointer hover:!bg-black/30' : 'bg-neutral-100 hover:cursor-default',
                        layout === FormSlideLayout.SINGLE_COLUMN_IMAGE_BACKGROUND ? 'absolute inset-0' : '',
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
                            <div className={cn('flex h-full items-center justify-center text-lg font-semibold', layout === FormSlideLayout.SINGLE_COLUMN_IMAGE_BACKGROUND ? 'absolute -top-[52%] left-0' : '')}>
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
