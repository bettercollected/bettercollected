import { FormTheme } from '@app/constants/theme';
import { StandardFormFieldDto } from '@app/models/dtos/form';
import SlideLayoutWrapper from '@app/views/organism/Layout/SlideLayoutWrapper';

import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { FormFieldComponent } from '../Form/FormSlide';
import { useEffect } from 'react';
import { useFormState } from '@app/store/jotai/form';
import { cn } from '@app/shadcn/util/lib';
import { FormSlideLayout } from '@app/models/enums/form';

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
                <div className="relative my-10 grid h-full w-full max-w-[800px] flex-1 grid-cols-1 content-center gap-20 px-5 lg:my-20 lg:px-20">
                    {slide?.properties?.fields?.map((field) => {
                        return <FormFieldComponent key={field.id} field={field} slideIndex={slide!.index} />;
                    })}
                </div>
            </div>
        </SlideLayoutWrapper>
    );
}
