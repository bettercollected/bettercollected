import Image from 'next/image';

import DemoImage from '@app/assets/image/rectangle.png';
import { FormField } from '@app/models/dtos/form';
import { useStandardForm } from '@app/store/jotai/fetchedForm';

import { FormFieldComponent } from '../Form/FormSlide';

export default function FormSlidePreview({ slide }: { slide: FormField }) {
    const { standardForm } = useStandardForm();

    return (
        <div
            className="grid min-h-screen w-full grid-cols-2"
            style={{ background: standardForm.theme?.accent }}
        >
            <div className="relative flex h-full flex-1 flex-col items-center justify-center ">
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
