'use client';

import React from 'react';

import { FormTheme } from '@app/constants/theme';
import useGetPageAttributes from '@app/lib/hooks/useGetPageAttributes';
import { useActiveSlideComponent } from '@app/store/jotai/activeBuilderComponent';
import { useFormState } from '@app/store/jotai/form';

import LayoutWrapper from './LayoutWrapper';

interface IGreetingLayoutWrapper {
    disabled?: boolean;
    greetingIndex: number;
    thankYouPageIndex?: number;
    children: React.ReactNode | React.ReactNode[];
    theme?: FormTheme;
}
const GreetingLayoutWrapper = ({
    disabled,
    greetingIndex,
    theme,
    children
}: IGreetingLayoutWrapper) => {
    const { activeSlideComponent } = useActiveSlideComponent();
    const { layout, imageUrl } = useGetPageAttributes(greetingIndex);
    const {
        updateWelcomePageImage,
        updateThankYouPageImage,
        updateThankYouPageLayout,
        updateWelcomePageLayout
    } = useFormState();

    return (
        <LayoutWrapper
            layout={layout}
            imageUrl={imageUrl}
            altImage={activeSlideComponent?.id || ''}
            updatePageImage={
                activeSlideComponent?.index === -10
                    ? updateWelcomePageImage
                    : updateThankYouPageImage
            }
            disabled={disabled}
            updatePageLayout={
                activeSlideComponent?.index === -10
                    ? updateWelcomePageLayout
                    : updateThankYouPageLayout
            }
            theme={theme}
        >
            {children}
        </LayoutWrapper>
    );
};

export default GreetingLayoutWrapper;
