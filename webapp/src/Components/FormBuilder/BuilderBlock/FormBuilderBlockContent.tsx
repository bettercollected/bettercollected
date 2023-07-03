import React from 'react';

import EndAdornmentInputField from '@Components/FormBuilder/EndAdornmentInputFIeld';
import LongText from '@Components/FormBuilder/LongText';
import MatrixField from '@Components/FormBuilder/MatrixField';
import RatingField from '@Components/FormBuilder/RatingField';
import StartAdornmentInputField from '@Components/FormBuilder/StartAdornmentInputField';

import { FormBuilderTagNames } from '@app/models/enums/formBuilder';

export default function FormBuilderBlockContent({ tag, position, reference }: any) {
    const renderBlockContent = () => {
        switch (tag) {
            case FormBuilderTagNames.INPUT_SHORT_TEXT:
                return <EndAdornmentInputField type="short_text" />;
            case FormBuilderTagNames.INPUT_LONG_TEXT:
                return <LongText />;
            case FormBuilderTagNames.INPUT_EMAIL:
                return <EndAdornmentInputField type="email" />;
            case FormBuilderTagNames.INPUT_NUMBER:
                return <EndAdornmentInputField type="number" />;
            case FormBuilderTagNames.INPUT_LINK:
                return <EndAdornmentInputField type="link" />;
            case FormBuilderTagNames.INPUT_DATE:
                return <EndAdornmentInputField type="date" />;
            case FormBuilderTagNames.INPUT_PHONE_NUMBER:
                return <EndAdornmentInputField type="phone_number" />;
            case FormBuilderTagNames.INPUT_CHECKBOXES:
                return <StartAdornmentInputField type="checkbox" />;
            case FormBuilderTagNames.INPUT_MULTIPLE_CHOICE:
                return <StartAdornmentInputField type="choice" />;
            case FormBuilderTagNames.INPUT_DROPDOWN:
                return <StartAdornmentInputField type="dropdown" />;
            case FormBuilderTagNames.INPUT_RANKING:
                return <StartAdornmentInputField type="ranking" />;
            case FormBuilderTagNames.INPUT_RATING:
                return <RatingField number={10} />;
            case FormBuilderTagNames.INPUT_MATRIX:
                return <MatrixField allowMultipleSelection={false} rows={[1, 2, 3]} columns={[1, 2, 3]} />;
            default:
                return null;
        }
    };

    return (
        <div className="w-full">
            <div data-position={position} data-tag={tag} ref={reference}>
                {renderBlockContent()}
            </div>
        </div>
    );
}
