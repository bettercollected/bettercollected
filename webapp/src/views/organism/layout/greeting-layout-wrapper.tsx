'use client';

import React from 'react';

import { FormTheme } from '@app/constants/theme';
import { useBuilderFormLogo } from '@app/lib/hooks/use-form-logo';
import useGetPageAttributes from '@app/lib/hooks/use-get-page-attributes';
import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { useActiveSlideComponent } from '@app/store/jotai/active-builder-component';
import { useFormState } from '@app/store/jotai/form';
import { greetingCover, hasPictureSlot } from '@app/views/molecules/theme/theme-artwork';

import LayoutWrapper from './layout-wrapper';

interface IGreetingLayoutWrapper {
    disabled?: boolean;
    greetingIndex: number;
    thankYouPageIndex?: number;
    children: React.ReactNode | React.ReactNode[];
    theme?: FormTheme;
}
const GreetingLayoutWrapper = ({ disabled, greetingIndex, theme, children }: IGreetingLayoutWrapper) => {
    const { activeSlideComponent } = useActiveSlideComponent();
    const { layout, imageUrl } = useGetPageAttributes(greetingIndex);
    const { updateWelcomePageImage, updateThankYouPageImage, updateThankYouPageLayout, updateWelcomePageLayout } = useFormState();
    const form = useAppSelector(selectForm);
    // The organisation logo as respondents will see it: larger on the welcome page.
    const logo = useBuilderFormLogo();
    const welcome = greetingIndex === -10;
    // As respondents see it: a welcome page beside the theme's artwork is its
    // cover, an ending without a picture half carries the artwork as a band.
    const cover = welcome ? greetingCover(theme, layout, imageUrl, { privateForm: !!form?.settings?.private }) : null;

    return (
        <LayoutWrapper
            showDesktopLayout
            layout={layout}
            imageUrl={imageUrl}
            altImage={activeSlideComponent?.id || ''}
            updatePageImage={activeSlideComponent?.index === -10 ? updateWelcomePageImage : updateThankYouPageImage}
            disabled={disabled}
            updatePageLayout={activeSlideComponent?.index === -10 ? updateWelcomePageLayout : updateThankYouPageLayout}
            theme={cover?.theme ?? theme}
            artworkTheme={theme}
            style={cover ? { ...cover.style, color: cover.theme.primary } : undefined}
            topAligned={theme?.style === 'leaflet'}
            logo={logo}
            logoSize={welcome ? 'cover' : 'page'}
            artworkBand={!welcome && !hasPictureSlot(layout)}
        >
            {children}
        </LayoutWrapper>
    );
};

export default GreetingLayoutWrapper;
