import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import DateField from '@app/views/molecules/ResponderFormFields/DateField';
import LinearRatingField from '@app/views/molecules/ResponderFormFields/LinearRating';
import RatingField from '@app/views/molecules/ResponderFormFields/RatingField';

import DropDownField from './DropDownFIeld';
import FileUpload from './FileUploadField';
import InputField from './InputField';
import YesNoField from './YesNoField';
import Image from 'next/image';
import ImageField from './Imagefield';
import VideoField from './VideoField';

export const renderImage = (field: StandardFormFieldDto) => {
    return field.imageUrl ? (
        <div className="relative my-2 max-h-[168px] w-full">
            <Image style={{ objectFit: 'contain', width: 'fit-content', maxHeight: '168px' }} sizes="100vw" src={field.imageUrl} alt={field.id + ' image'} height={0} width={0} priority />
        </div>
    ) : (
        <></>
    );
};

function renderFieldWrapper(field: StandardFormFieldDto, slide: StandardFormFieldDto, disabled: boolean) {
    return (
        <div className="relative h-full w-full space-y-2">
            {renderImage(field)}
            {renderField(field, slide, disabled)}
        </div>
    );
}

function renderField(field: StandardFormFieldDto, slide: StandardFormFieldDto, disabled: boolean) {
    switch (field.type) {
        case FieldTypes.EMAIL:
        case FieldTypes.NUMBER:
        case FieldTypes.SHORT_TEXT:
        case FieldTypes.LONG_TEXT:
        case FieldTypes.LINK:
        case FieldTypes.PHONE_NUMBER:
            return <InputField field={field} slide={slide} disabled={disabled} />;
        case FieldTypes.FILE_UPLOAD:
            return <FileUpload field={field} slide={slide} disabled={disabled} />;
        case FieldTypes.YES_NO:
            return <YesNoField field={field} slide={slide} disabled={disabled} />;
        case FieldTypes.DROP_DOWN:
        case FieldTypes.MULTIPLE_CHOICE:
            return <DropDownField field={field} slide={slide} disabled={disabled} />;
        case FieldTypes.TEXT:
            return <></>;
        case FieldTypes.RATING:
            return <RatingField field={field} slide={slide} isBuilder={true} />;
        case FieldTypes.DATE:
            return <DateField field={field} slide={slide} isBuilder={true} />;
        case FieldTypes.LINEAR_RATING:
            return <LinearRatingField field={field} slide={slide} isBuilder={true} />;
        case FieldTypes.IMAGE_CONTENT:
            return <ImageField isBuilder field={field} />;
        case FieldTypes.VIDEO_CONTENT:
            return <VideoField isBuilder field={field} />;
        default:
            return null;
    }
}

export default renderFieldWrapper;
