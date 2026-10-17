'use client';

import React from 'react';

import { FormTheme } from '@app/constants/theme';
import { useBuilderFormLogo } from '@app/lib/hooks/use-form-logo';
import useGetPageAttributes from '@app/lib/hooks/use-get-page-attributes';
import { useActiveSlideComponent } from '@app/store/jotai/active-builder-component';
import { useFormState } from '@app/store/jotai/form';

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
    // The organisation logo as respondents will see it: larger on the welcome page.
    const logo = useBuilderFormLogo();

    return (
        <LayoutWrapper
            showDesktopLayout
            layout={layout}
            imageUrl={imageUrl}
            altImage={activeSlideComponent?.id || ''}
            updatePageImage={activeSlideComponent?.index === -10 ? updateWelcomePageImage : updateThankYouPageImage}
            disabled={disabled}
            updatePageLayout={activeSlideComponent?.index === -10 ? updateWelcomePageLayout : updateThankYouPageLayout}
            theme={theme}
            topAligned={theme?.style === 'leaflet'}
            logo={logo}
            logoSize={greetingIndex === -10 ? 'cover' : 'page'}
        >
            {children}
        </LayoutWrapper>
    );
};

export default GreetingLayoutWrapper;
