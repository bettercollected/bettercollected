'use client';

import React from 'react';

import useGetPageAttributes from '@app/lib/hooks/useGetPageAttributes';
import { useActiveSlideComponent } from '@app/store/jotai/activeBuilderComponent';
import { useFormState } from '@app/store/jotai/form';

import LayoutWrapper from './LayoutWrapper';

interface IGreetingLayoutWrapper {
    disabled?: boolean;
    greetingIndex: number;
    thankYouPageIndex?: number;
    children: React.ReactNode | React.ReactNode[];
}
const GreetingLayoutWrapper = ({
    disabled,
    greetingIndex,
    thankYouPageIndex,
    children
}: IGreetingLayoutWrapper) => {
    const { activeSlideComponent } = useActiveSlideComponent();
    const { layout, imageUrl } = useGetPageAttributes(greetingIndex);
    const { updateWelcomePageImage, updateThankYouPageImage } = useFormState();

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
        >
            {children}
        </LayoutWrapper>
    );
};

export default GreetingLayoutWrapper;
