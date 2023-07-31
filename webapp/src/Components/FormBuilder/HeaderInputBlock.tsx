import React, { ChangeEvent, FormEvent } from 'react';

import { useTranslation } from 'next-i18next';

import CustomContentEditable from '@Components/FormBuilder/ContentEditable/CustomContentEditable';
import { useDispatch } from 'react-redux';

import useFormBuilderState from '@app/containers/form-builder/context';
import useBuilderTranslation from '@app/lib/hooks/use-builder-translation';
import { FormBuilderTagNames } from '@app/models/enums/formBuilder';
import { setBuilderState, setUpdateField } from '@app/store/form-builder/actions';
import { selectBuilderState } from '@app/store/form-builder/selectors';
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
            return '5';
        case FormBuilderTagNames.LAYOUT_HEADER4:
            return '4';
        case FormBuilderTagNames.LAYOUT_HEADER3:
            return '3';
        case FormBuilderTagNames.LAYOUT_HEADER2:
            return '2';
        case FormBuilderTagNames.LAYOUT_HEADER1:
            return '1';
        case FormBuilderTagNames.LAYOUT_LABEL:
            return 'LABEL';
        default:
            return '';
    }
};
export default function HeaderInputBlock({ field, id, position }: IHeaderInputBlockProps) {
    const dispatch = useDispatch();
    const builderState = useAppSelector(selectBuilderState);
    const { setBackspaceCount } = useFormBuilderState();
    const { t } = useBuilderTranslation();

    const activeFieldIndex = builderState.activeFieldIndex;
    const onChange = (event: FormEvent<HTMLElement>) => {
        setBackspaceCount(0);
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
            placeholder={'COMPONENTS.HEADER.' + t(getPlaceholder(field?.type))}
            onFocusCallback={(event: React.FocusEvent<HTMLElement>) => {
                dispatch(setBuilderState({ activeFieldIndex: position }));
            }}
        />
    );
}
