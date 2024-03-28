import { FormField } from '@app/models/dtos/form';
import { useStandardForm } from '@app/store/jotai/fetchedForm';

import { FormFieldComponent } from '../Form/FormSlide';

export default function FormSlidePreview({ slide }: { slide: FormField }) {
    const { standardForm } = useStandardForm();

    return (
        <div
            className="flex min-h-screen w-full items-center"
            style={{ background: standardForm.theme?.accent }}
        >
            <div className="relative flex h-full max-w-[800px] flex-1 flex-col items-start justify-center gap-20 px-5 lg:px-20">
                {slide?.properties?.fields?.map((field) => {
                    return (
                        <FormFieldComponent
                            key={field.id}
                            field={field}
                            slideIndex={slide!.index}
                        />
                    );
                })}
            </div>
        </div>
    );
}
