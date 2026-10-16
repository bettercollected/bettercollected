'use client';

import { FormTheme } from '@app/constants/theme';
import { StandardFormFieldDto } from '@app/models/dtos/form';
import SlideLayoutWrapper from '@app/views/organism/layout/slide-layout-wrapper';

import { cn } from '@app/shadcn/util/lib';
import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { useFormState } from '@app/store/jotai/form';
import { useEffect } from 'react';
import { FormFieldComponent } from '../form/form-slide';
import { FORM_COLUMN, clampSpan, columnPlacementClass, fieldSpacingClass } from '../layout/form-column';

export default function FormSlidePreview({ slide, theme }: { slide: StandardFormFieldDto; theme?: FormTheme }) {
    const standardForm = useAppSelector(selectForm);
    const { updateFormTheme, theme: a } = useFormState();
    useEffect(() => {
        standardForm.theme && updateFormTheme(standardForm?.theme);
    }, [standardForm.formId]);
    const slideTheme = theme ? theme : standardForm.theme;
    return (
        <SlideLayoutWrapper showDesktopLayout slide={slide} theme={slideTheme} disabled>
            {/* Same column and question rhythm as the builder canvas and the live form (form-column.ts). */}
            <div className={cn(FORM_COLUMN, columnPlacementClass(slide?.properties?.layout), 'relative flex flex-col gap-12 pt-12 lg:grid lg:grid-cols-12 lg:gap-x-6 lg:gap-y-12')}>
                {(slide?.properties?.fields ?? []).map((field, position, fields) => {
                    const span = clampSpan(field);
                    return (
                        <div key={field.id} className={cn('min-w-0', fieldSpacingClass(field, position === fields.length - 1))} style={{ gridColumn: `span ${span} / span ${span}` }}>
                            <FormFieldComponent field={field} slideIndex={slide!.index} />
                        </div>
                    );
                })}
            </div>
        </SlideLayoutWrapper>
    );
}
