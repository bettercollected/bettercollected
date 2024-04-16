import { FieldTypes, FormField } from '@app/models/dtos/form';
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

export const renderImage = (field: FormField) => {
    return field.imageUrl ? (
        <div className="relative">
            <div className=" aspect-video h-[168px] w-full">
                <Image style={{ objectFit: 'cover' }} src={field.imageUrl} alt={field.id + ' image'} fill priority />
            </div>
        </div>
    ) : (
        <></>
    );
};

function renderFieldWrapper(field: FormField, slide: FormField, disabled: boolean) {
    return (
        <div className="relative h-full w-full space-y-2">
            {renderImage(field)}
            {renderField(field, slide, disabled)}
        </div>
    );
}

function renderField(field: FormField, slide: FormField, disabled: boolean) {
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
