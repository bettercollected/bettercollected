import React, { FormEvent } from 'react';

import CustomContentEditable from '@Components/FormBuilder/ContentEditable/CustomContentEditable';
import { useDispatch } from 'react-redux';

import useFormBuilderState from '@app/containers/form-builder/context';
import useBuilderTranslation from '@app/lib/hooks/use-builder-translation';
import useUserTypingDetection from '@app/lib/hooks/use-user-typing-detection';
import useUndoRedo from '@app/lib/use-undo-redo';
import { FormBuilderTagNames } from '@app/models/enums/formBuilder';
import { setBuilderState, setUpdateField } from '@app/store/form-builder/actions';
import { contentEditableClassNames } from '@app/utils/formBuilderBlockUtils';

interface IHeaderInputBlockProps {
    field: any;
    id: any;
    position: number;
}

const getPlaceholder = (type: FormBuilderTagNames) => {
    switch (type) {
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
    const { setBackspaceCount } = useFormBuilderState();
    const { t } = useBuilderTranslation();
    const { handleUserTypingEnd } = useUserTypingDetection();
    const { isUndoRedoInProgress } = useUndoRedo();

    const onChange = (event: FormEvent<HTMLElement>) => {
        if (isUndoRedoInProgress) return;
        setBackspaceCount(0);
        dispatch(
            setUpdateField({
                ...field,
                value: event.currentTarget.innerText
            })
        );
        handleUserTypingEnd();
    };
    return (
        <CustomContentEditable
            type={field?.type}
            tagName="p"
            position={position}
            id={id}
            value={field?.value || ''}
            className={'w-full  ' + contentEditableClassNames(false, field?.type, true)}
            onChangeCallback={onChange}
            placeholder={t('COMPONENTS.HEADER.' + getPlaceholder(field?.type))}
            onFocusCallback={(event: React.FocusEvent<HTMLElement>) => {
                dispatch(setBuilderState({ activeFieldIndex: position }));
            }}
        />
    );
}
