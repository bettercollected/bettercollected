'use client';
import { StandardFormFieldDto } from '@app/models/dtos/form';
import QuestionWrapper from '@app/views/molecules/ResponderFormFields/QuestionQwrapper';
import Image from 'next/image';

const ImageField = ({ field, isBuilder = false }: { field: StandardFormFieldDto; isBuilder?: boolean }) => {
    return isBuilder ? (
        <div className="h-40 w-full">
            <Image style={{ objectFit: 'cover' }} fill src={field?.attachment?.href ?? ''} alt={field.id + ' image'} />
        </div>
    ) : (
        <QuestionWrapper field={field}>
            <div className="relative h-40 w-full">
                <Image style={{ objectFit: 'cover' }} fill src={field?.attachment?.href ?? ''} alt={field.id + ' image'} />
            </div>
        </QuestionWrapper>
    );
};

export default ImageField;
