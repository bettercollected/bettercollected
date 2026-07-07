'use client';

import { FormTheme } from '@app/constants/theme';
import { StandardFormFieldDto } from '@app/models/dtos/form';
import SlideLayoutWrapper from '@app/views/organism/layout/slide-layout-wrapper';

import { FormSlideLayout } from '@app/models/enums/form';
import { cn } from '@app/shadcn/util/lib';
import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { useFormState } from '@app/store/jotai/form';
import { useEffect } from 'react';
import { FormFieldComponent } from '../form/form-slide';

export default function FormSlidePreview({ slide, theme }: { slide: StandardFormFieldDto; theme?: FormTheme }) {
    const standardForm = useAppSelector(selectForm);
    const { updateFormTheme, theme: a } = useFormState();
    useEffect(() => {
        standardForm.theme && updateFormTheme(standardForm?.theme);
    }, [standardForm.formId]);
    const slideTheme = theme ? theme : standardForm.theme;
    return (
        <SlideLayoutWrapper showDesktopLayout slide={slide} theme={slideTheme} disabled>
            <div className={cn('flex w-full ', slide?.properties?.layout === FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND_LEFT_ALIGN ? 'justify-start' : 'justify-center')}>
                {/* Same 64px group rhythm as the builder canvas and the live form. */}
                <div className="relative my-10 grid h-full w-full max-w-[800px] flex-1 grid-cols-1 content-center gap-16 px-5 lg:my-20 lg:px-20">
                    {slide?.properties?.fields?.map((field) => {
                        return <FormFieldComponent key={field.id} field={field} slideIndex={slide!.index} />;
                    })}
                </div>
            </div>
        </SlideLayoutWrapper>
    );
}
