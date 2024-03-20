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
            <div className=" flex h-full flex-col items-center justify-center py-4">
                <div className=" flex h-full w-full max-w-[800px] flex-col  gap-20 px-10 py-20">
                    {slide?.properties?.fields?.map((field) => {
                        return (
                            <FormFieldComponent
                                field={field}
                                slideIndex={slide!.index}
                            />
                        );
                    })}
                </div>
            </div>
            <div className="relative h-full w-full">
                <Image
                    src={DemoImage}
                    alt="Demo Image"
                    fill
                    style={{
                        objectFit: 'cover'
                    }}
                    priority
                    sizes="(min-w: 0px) 100%"
                />
            </div>
        </div>
    );
}
