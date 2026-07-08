'use client';

import React from 'react';

import { FormTheme } from '@app/constants/theme';
import { StandardFormFieldDto } from '@app/models/dtos/form';
import useFormFieldsAtom from '@app/store/jotai/field-selectors';

import LayoutWrapper from './layout-wrapper';

interface ISlideLayoutWrapperProps {
    slide: StandardFormFieldDto;
    children: React.ReactNode | React.ReactNode[];
    disabled?: boolean;
    theme?: FormTheme;
    scrollDivId?: string;
    showDesktopLayout?: boolean;
}

export default function SlideLayoutWrapper({ slide, children, theme, disabled = false, scrollDivId, showDesktopLayout }: ISlideLayoutWrapperProps) {
    const { updateSlideImage, updateSlideLayout } = useFormFieldsAtom();

    // A slide-level theme (when present) wins over the form theme — resolved
    // once here so both the outer style and the LayoutWrapper ground agree.
    const effectiveTheme = slide?.properties?.theme?.accent ? slide?.properties?.theme : theme;
    const style = {
        backgroundColor: effectiveTheme?.accent
    };

    return (
        <LayoutWrapper
            showDesktopLayout={showDesktopLayout}
            layout={slide?.properties?.layout}
            imageUrl={slide?.imageUrl}
            altImage={slide?.id}
            disabled={disabled}
            updatePageImage={updateSlideImage}
            updatePageLayout={updateSlideLayout}
            style={style}
            theme={effectiveTheme}
            scrollDivId={scrollDivId}
        >
            {children}
        </LayoutWrapper>
    );
}
