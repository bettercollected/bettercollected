'use client';

import React from 'react';

import { FormTheme } from '@app/constants/theme';
import { FormField } from '@app/models/dtos/form';
import useFormFieldsAtom from '@app/store/jotai/fieldSelector';

import LayoutWrapper from './LayoutWrapper';

interface ISlideLayoutWrapperProps {
    slide: FormField;
    children: React.ReactNode | React.ReactNode[];
    disabled?: boolean;
    theme?: FormTheme;
    scrollDivId?: string;
}

export default function SlideLayoutWrapper({
    slide,
    children,
    theme,
    disabled = false,
    scrollDivId
}: ISlideLayoutWrapperProps) {
    const { updateSlideImage, updateSlideLayout } = useFormFieldsAtom();

    const style = {
        backgroundColor: slide?.properties?.theme?.accent || theme?.accent
    };

    return (
        <LayoutWrapper
            layout={slide?.properties?.layout}
            imageUrl={slide?.imageUrl}
            altImage={slide?.id}
            disabled={disabled}
            updatePageImage={updateSlideImage}
            updatePageLayout={updateSlideLayout}
            style={style}
            theme={theme}
            scrollDivId={scrollDivId}
        >
            {children}
        </LayoutWrapper>
    );
}
