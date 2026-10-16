'use client';

import { useState } from 'react';

import Image from 'next/image';

import DeleteIcon from '@Components/icons/delete';
import { SwitchIcon } from '@Components/icons/switch-icon';

import { FormTheme } from '@app/constants/theme';
import { useDialogModal } from '@app/lib/hooks/use-dialog-modal';
import { FormSlideLayout } from '@app/models/enums/form';
import { Button } from '@app/shadcn/components/ui/button';
import { ScrollArea } from '@app/shadcn/components/ui/scroll-area';
import { cn } from '@app/shadcn/util/lib';
import { ResolvedFormLogo } from '@app/utils/form-logo';
import FormLogoStrip from '@app/views/molecules/form/form-logo-strip';
import { themeBackgroundStyle } from '@app/views/molecules/theme/theme-shared';
import { FORM_GUTTER } from '@app/views/organism/layout/form-column';

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
    /**
     * Start the page at the top instead of centring it: pages that open with
     * a full-width bar (the Leaflet style's section bar) draw it from the top
     * edge of the page.
     */
    topAligned?: boolean;
    /**
     * The organisation logo strip at the top of the page (form-logo-strip.tsx):
     * above the scrolling content, in the content's half of the page, so it
     * lines up with the form column and the page header sits under it.
     */
    logo?: ResolvedFormLogo | null;
    /** `cover` on the welcome page, `page` elsewhere. */
    logoSize?: 'cover' | 'page';
}

const LayoutWrapper = ({ layout, theme, imageUrl, updatePageImage, updatePageLayout, altImage, disabled = false, style = {}, scrollDivId, children, showDesktopLayout = false, topAligned = false, logo, logoSize = 'page' }: ILayoutWrapper) => {
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
                        layout === FormSlideLayout.SINGLE_COLUMN_IMAGE_BACKGROUND ? 'backdrop-blur-lg rounded-[8px] opacity-50' : 'opacity-100'
                    )}
                    src={imageUrl}
                    alt={altImage + ' image'}
                    loader={
                        imageUrl.startsWith('https://images.unsplash.com/')
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
                        <div className="z-10 cursor-pointer rounded-md bg-white p-2 shadow-large" onClick={handleRemoveImage}>
                            <DeleteIcon width={24} height={24} />
                        </div>
                        <div className="z-10 cursor-pointer rounded-md bg-white p-2 shadow-large" onClick={handleChangeImage}>
                            <SwitchIcon />
                        </div>
                    </div>
                )}
            </>
        );
    };
    // The content's place in a two-column layout (the image takes the other half).
    const contentOrder = layout && layout === FormSlideLayout.TWO_COLUMN_IMAGE_LEFT ? 'order-1' : layout && layout === FormSlideLayout.TWO_COLUMN_IMAGE_RIGHT ? 'order-0' : '';
    const scrollArea = (
        <ScrollArea
            thumbBg={theme?.tertiary}
            id={scrollDivId}
            style={
                // On the image-background layout the slide's own image is
                // the ground, so the theme background stays out of the way.
                layout === FormSlideLayout.SINGLE_COLUMN_IMAGE_BACKGROUND ? { background: 'transparent' } : themeBackgroundStyle(theme)
            }
            className={cn(
                // Under a logo strip the column holding both sets the height.
                logo ? 'relative min-h-0 grow' : 'relative grow lg:min-h-[100%]',
                // Radix wraps the viewport's content in a `display: table`
                // box of content height, which defeated every attempt to
                // centre a page vertically (the welcome page sat pinned to
                // the top with an empty band below it). Make that box a
                // full-height flex column the page can grow into.
                '[&>[data-radix-scroll-area-viewport]>div]:flex! [&>[data-radix-scroll-area-viewport]>div]:min-h-full [&>[data-radix-scroll-area-viewport]>div]:flex-col',
                disabled ? 'overflow-hidden' : '',
                layout && layout === FormSlideLayout.SINGLE_COLUMN_IMAGE_BACKGROUND ? 'z-10 bg-transparent!' : '',
                logo ? '' : contentOrder
            )}
        >
            {/* One side gutter on every page (form-column.ts). Content
            shorter than the screen sits optically centred: the free
            space above and below splits 2:3, a little above the true
            centre. Longer content starts at the top and scrolls.
            A named container, so a page can lay itself out by the
            room it actually has (the builder canvas is narrower
            than the window). */}
            <div className={cn(FORM_GUTTER, '@container/page flex w-full grow flex-col', topAligned ? 'pb-8 lg:pb-12' : "py-8 before:flex-[2] before:content-[''] after:flex-[3] after:content-[''] lg:py-12")}>{children}</div>
        </ScrollArea>
    );

    return (
        <>
            <div
                style={{
                    backgroundColor: theme?.accent,
                    // Focus outlines inside a form wear the theme's action colour
                    // (the global focus rule in tailwind.css reads --focus-ring).
                    ...(theme?.secondary ? { ['--focus-ring' as string]: theme.secondary } : {}),
                    ...style
                }}
                className={cn(
                    showDesktopLayout ? 'grid' : 'flex lg:grid',
                    // Forms keep their own typeface (Public Sans): the app's Instrument
                    // Sans stays out of what respondents see (DESIGN.md §2, §9).
                    // Square: the trust strip now sits directly below, in flow; the
                    // preview and canvas frames round their own corners.
                    'relative h-full w-full grow overflow-hidden bg-transparent! font-form',
                    layout === FormSlideLayout.TWO_COLUMN_IMAGE_RIGHT ? 'flex-col-reverse justify-end' : 'flex-col justify-end',
                    layout === FormSlideLayout.TWO_COLUMN_IMAGE_LEFT || layout === FormSlideLayout.TWO_COLUMN_IMAGE_RIGHT ? 'grid-cols-2' : 'grid-cols-1',
                    disabled ? 'h-full overflow-hidden' : ''
                )}
            >
                {logo ? (
                    <div className={cn('relative flex min-h-0 grow flex-col', showDesktopLayout ? 'h-full' : 'lg:h-full', layout === FormSlideLayout.SINGLE_COLUMN_IMAGE_BACKGROUND && 'z-10', contentOrder)}>
                        <FormLogoStrip logo={logo} theme={theme} layout={layout} size={logoSize} />
                        {scrollArea}
                    </div>
                ) : (
                    scrollArea
                )}
                {/* Image with controls works for left and right image layout */}
                {layout && layout !== FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND && layout !== FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND_LEFT_ALIGN && layout !== FormSlideLayout.SINGLE_COLUMN_IMAGE_BACKGROUND && (
                    <div
                        className={cn(
                            'relative',
                            showDesktopLayout ? 'h-auto' : 'h-[30%] lg:h-auto',
                            (layout && layout === FormSlideLayout.TWO_COLUMN_IMAGE_LEFT) || (layout && layout === FormSlideLayout.TWO_COLUMN_IMAGE_RIGHT) ? 'grid-cols-1' : '',
                            imageUrl && !disabled ? 'hover:cursor-pointer hover:bg-black/30!' : 'bg-neutral-100 hover:cursor-default'
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
                        imageUrl && !disabled ? 'hover:cursor-pointer hover:bg-black/30!' : 'bg-neutral-100 hover:cursor-default',
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
                            <div className={cn('flex h-full items-center justify-center text-lg font-semibold', layout === FormSlideLayout.SINGLE_COLUMN_IMAGE_BACKGROUND ? 'absolute top-[-52%] left-0' : '')}>
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
