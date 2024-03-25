'use client';

import React from 'react';

import useGetPageAttributes from '@app/lib/hooks/useGetPageAttributes';
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
    const { layout, imageUrl } = useGetPageAttributes(slide.index);
    const { updateSlideImage } = useFormFieldsAtom();
    const { theme } = useFormState();

    const style = {
        backgroundColor: slide.properties?.theme?.accent || theme?.accent
    };

    return (
        <LayoutWrapper
            layout={layout}
            imageUrl={imageUrl}
            altImage={slide.id}
            disabled={disabled}
            updatePageImage={updateSlideImage}
            style={style}
        >
            {children}
        </LayoutWrapper>
    );
}
