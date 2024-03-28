'use client';

import React from 'react';

import { FormField } from '@app/models/dtos/form';
import useFormFieldsAtom from '@app/store/jotai/fieldSelector';
import { useFormState } from '@app/store/jotai/form';

import LayoutWrapper from './LayoutWrapper';

interface ISlideLayoutWrapperProps {
    slide: FormField;
    children: React.ReactNode | React.ReactNode[];
    disabled?: boolean;
}

export default function SlideLayoutWrapper({
    slide,
    children,
    disabled = false
}: ISlideLayoutWrapperProps) {
    const { updateSlideImage } = useFormFieldsAtom();
    const { theme } = useFormState();

    const style = {
        backgroundColor: slide.properties?.theme?.accent || theme?.accent
    };

    return (
        <LayoutWrapper
            layout={slide?.properties?.layout}
            imageUrl={slide?.imageUrl}
            altImage={slide.id}
            disabled={disabled}
            updatePageImage={updateSlideImage}
            style={style}
        >
            {children}
        </LayoutWrapper>
    );
}
