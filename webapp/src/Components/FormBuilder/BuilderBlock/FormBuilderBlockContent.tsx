import React from 'react';

import EndAdornmentInputField from '@Components/FormBuilder/EndAdornmentInputFIeld';
import FileUpload from '@Components/FormBuilder/FileUpload';
import HeaderInputBlock from '@Components/FormBuilder/HeaderInputBlock';
import LongText from '@Components/FormBuilder/LongText';
import MultipleChoice from '@Components/FormBuilder/MultipleChoice';
import RatingField from '@Components/FormBuilder/RatingField';
import LabelTagValidator from '@Components/HOCs/LabelTagValidator';
import MultipleChoiceKeyEventListener from '@Components/Listeners/MultipleChoiceKeyListener';

import { FormBuilderTagNames } from '@app/models/enums/formBuilder';
import { setActiveField } from '@app/store/form-builder/actions';
import { useAppDispatch } from '@app/store/hooks';

import MarkdownEditor from '../MarkdownEditor';

interface IFormBuilderBlockContent {
    type: string;
    position: number;
    id: string;
    field: any;
}

export default function FormBuilderBlockContent({ type, position, field, id }: IFormBuilderBlockContent) {
    const dispatch = useAppDispatch();

    const renderBlockContent = (position: number) => {
        switch (type) {
            case FormBuilderTagNames.LAYOUT_HEADER1:
            case FormBuilderTagNames.LAYOUT_HEADER2:
            case FormBuilderTagNames.LAYOUT_HEADER3:
            case FormBuilderTagNames.LAYOUT_HEADER4:
            case FormBuilderTagNames.LAYOUT_LABEL:
                return <HeaderInputBlock field={field} id={id} position={position} />;
            case FormBuilderTagNames.LAYOUT_MARKDOWN:
                return <MarkdownEditor field={field} id={id} />;
            case FormBuilderTagNames.INPUT_SHORT_TEXT:
            case FormBuilderTagNames.INPUT_EMAIL:
            case FormBuilderTagNames.INPUT_NUMBER:
            case FormBuilderTagNames.INPUT_LINK:
            case FormBuilderTagNames.INPUT_PHONE_NUMBER:
                return <EndAdornmentInputField field={field} id={id} position={position} />;
            case FormBuilderTagNames.INPUT_DATE:
                return <EndAdornmentInputField field={field} id={id} position={position} placeholder="Enter Helper text" />;
            case FormBuilderTagNames.INPUT_LONG_TEXT:
                return <LongText field={field} id={id} position={position} />;
            case FormBuilderTagNames.INPUT_CHECKBOXES:
            case FormBuilderTagNames.INPUT_MULTIPLE_CHOICE:
            case FormBuilderTagNames.INPUT_DROPDOWN:
            case FormBuilderTagNames.INPUT_RANKING:
                return (
                    <MultipleChoiceKeyEventListener field={field}>
                        <MultipleChoice field={field} id={id} position={position} />
                    </MultipleChoiceKeyEventListener>
                );
            case FormBuilderTagNames.INPUT_RATING:
                return <RatingField field={field} id={id} />;
            case FormBuilderTagNames.INPUT_MEDIA:
                return <FileUpload field={field} id={id} />;
            default:
                return null;
        }
    };

    const renderValidatedBlockContent = (position: number) => {
        if (type !== FormBuilderTagNames.LAYOUT_LABEL) {
            return <LabelTagValidator position={position}> {renderBlockContent(position)}</LabelTagValidator>;
        }
        return renderBlockContent(position);
    };
    return (
        <div className="w-full relative">
            <div
                data-position={position}
                data-tag={type}
                onFocus={() => {
                    dispatch(setActiveField({ position: field?.position, id: field?.id }));
                }}
            >
                {renderValidatedBlockContent(position)}
            </div>
        </div>
    );
}
