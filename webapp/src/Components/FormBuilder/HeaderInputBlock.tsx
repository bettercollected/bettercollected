import React, { ChangeEvent, useEffect, useRef } from 'react';

import { useDispatch } from 'react-redux';

import { FormBuilderTagNames } from '@app/models/enums/formBuilder';
import { setUpdateField } from '@app/store/form-builder/actions';
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
    const inputRef = useRef<HTMLInputElement>(null);
    const dispatch = useDispatch();
    const builderState = useAppSelector(selectBuilderState);

    const activeFieldIndex = builderState.activeFieldIndex;
    useEffect(() => {
        // Focus on the first contentEditable element (title) when the page loads
        if (position !== activeFieldIndex) return;

        inputRef?.current?.focus();

        // Set the cursor position to 0 when the page loads
        const range = document.createRange();

        if (inputRef?.current) {
            range.selectNodeContents(inputRef.current);
            range.collapse(true);
        }
        const selection = window.getSelection();
        if (selection) {
            selection.removeAllRanges();
            selection.addRange(range);
        }
    }, [position, activeFieldIndex]);
    const onChange = (event: ChangeEvent<HTMLInputElement>) => {
        dispatch(setUpdateField({ ...field, value: event.target.value }));
    };
    return <input id={id} value={field.value || ''} ref={inputRef} className={'w-full ' + contentEditableClassNames(false, field.type)} onChange={onChange} placeholder={getPlaceholder(field.type)} />;
}
