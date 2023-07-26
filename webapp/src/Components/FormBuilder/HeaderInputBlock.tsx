import React, { ChangeEvent, useEffect, useRef } from 'react';

import CustomContentEditable from '@Components/FormBuilder/ContentEditable/CustomContentEditable';
import { Input } from '@mui/base';
import { useDispatch } from 'react-redux';

import useFormBuilderState from '@app/containers/form-builder/context';
import { FormBuilderTagNames } from '@app/models/enums/formBuilder';
import { setBuilderState, setUpdateField } from '@app/store/form-builder/actions';
import { selectBuilderState } from '@app/store/form-builder/selectors';
import { updateField } from '@app/store/form-builder/slice';
import { useAppSelector } from '@app/store/hooks';
import { contentEditableClassNames } from '@app/utils/formBuilderBlockUtils';

interface IHeaderInputBlockProps {
    field: any;
    id: any;
    position: number;
}

const getPlaceholder = (type: FormBuilderTagNames) => {
    switch (type) {
        case FormBuilderTagNames.LAYOUT_HEADER5:
            return 'Header 5';
        case FormBuilderTagNames.LAYOUT_HEADER4:
            return 'Header 4';
        case FormBuilderTagNames.LAYOUT_HEADER3:
            return 'Header 3';
        case FormBuilderTagNames.LAYOUT_HEADER2:
            return 'Header 2';
        case FormBuilderTagNames.LAYOUT_HEADER1:
            return 'Header 1';
        case FormBuilderTagNames.LAYOUT_LABEL:
            return 'Label';
        default:
            return '';
    }
};
export default function HeaderInputBlock({ field, id, position }: IHeaderInputBlockProps) {
    const dispatch = useDispatch();
    const builderState = useAppSelector(selectBuilderState);
    const { setBackspaceCount } = useFormBuilderState();

    const activeFieldIndex = builderState.activeFieldIndex;
    const onChange = (event: ChangeEvent<any>) => {
        setBackspaceCount(0);
        if (event?.currentTarget?.innerText)
            dispatch(
                setUpdateField({
                    ...field,
                    value: event.currentTarget.innerText
                })
            );
    };
    return (
        <CustomContentEditable
            type={field?.type}
            activeFieldIndex={activeFieldIndex}
            tagName="p"
            position={position}
            id={id}
            value={field?.value || ''}
            className={'w-full  ' + contentEditableClassNames(false, field?.type)}
            onChangeCallback={onChange}
            placeholder={getPlaceholder(field?.type)}
            onFocusCallback={(event: React.FocusEvent<HTMLElement>) => {
                dispatch(setBuilderState({ activeFieldIndex: position }));
            }}
        />
    );
}
