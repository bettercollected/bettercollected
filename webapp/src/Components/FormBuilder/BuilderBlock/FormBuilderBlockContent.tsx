import React from 'react';

import EndAdornmentInputField from '@Components/FormBuilder/EndAdornmentInputFIeld';
import HeaderInputBlock from '@Components/FormBuilder/HeaderInputBlock';
import LongText from '@Components/FormBuilder/LongText';
import MultipleChoice from '@Components/FormBuilder/MultipleChoice';
import RatingField from '@Components/FormBuilder/RatingField';

import { FormBuilderTagNames } from '@app/models/enums/formBuilder';
import { setActiveFieldIndex } from '@app/store/form-builder/slice';
import { useAppDispatch } from '@app/store/hooks';

export default function FormBuilderBlockContent({ type, position, reference, field, id }: any) {
    const dispatch = useAppDispatch();
    const renderBlockContent = () => {
        switch (type) {
            case FormBuilderTagNames.LAYOUT_HEADER1:
            case FormBuilderTagNames.LAYOUT_HEADER2:
            case FormBuilderTagNames.LAYOUT_HEADER3:
            case FormBuilderTagNames.LAYOUT_HEADER4:
            case FormBuilderTagNames.LAYOUT_HEADER5:
            case FormBuilderTagNames.LAYOUT_LABEL:
                return <HeaderInputBlock field={field} id={id} />;
            case FormBuilderTagNames.INPUT_SHORT_TEXT:
            case FormBuilderTagNames.INPUT_EMAIL:
            case FormBuilderTagNames.INPUT_NUMBER:
            case FormBuilderTagNames.INPUT_LINK:
            case FormBuilderTagNames.INPUT_DATE:
            case FormBuilderTagNames.INPUT_PHONE_NUMBER:
                return <EndAdornmentInputField field={field} id={id} />;
            case FormBuilderTagNames.INPUT_LONG_TEXT:
                return <LongText field={field} id={id} />;
            case FormBuilderTagNames.INPUT_CHECKBOXES:
            case FormBuilderTagNames.INPUT_MULTIPLE_CHOICE:
            case FormBuilderTagNames.INPUT_DROPDOWN:
            case FormBuilderTagNames.INPUT_RANKING:
                return <MultipleChoice field={field} id={id} />;
            case FormBuilderTagNames.INPUT_RATING:
                return <RatingField field={field} id={id} />;
            default:
                return null;
        }
    };

    return (
        <div
            className="w-full"
            onClick={() => {
                dispatch(setActiveFieldIndex(position));
            }}
        >
            <div data-position={position} data-tag={type} ref={reference}>
                {renderBlockContent()}
            </div>
        </div>
    );
}
