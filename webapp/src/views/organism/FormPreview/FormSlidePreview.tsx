import { FormTheme } from '@app/constants/theme';
import { FormField } from '@app/models/dtos/form';
import SlideLayoutWrapper from '@app/views/organism/Layout/SlideLayoutWrapper';

import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { FormFieldComponent } from '../Form/FormSlide';

export default function FormSlidePreview({ slide, theme }: { slide: FormField; theme?: FormTheme }) {
    const standardForm = useAppSelector(selectForm);

    const slideTheme = theme ? theme : standardForm.theme;
    return (
        <SlideLayoutWrapper slide={slide} theme={slideTheme} disabled>
            <div className="relative my-10 flex h-full max-w-[800px] flex-1 flex-col items-start justify-center gap-20 px-5 lg:my-20 lg:px-20">
                {slide?.properties?.fields?.map((field) => {
                    return <FormFieldComponent key={field.id} field={field} slideIndex={slide!.index} />;
                })}
            </div>
        </SlideLayoutWrapper>
    );
}
