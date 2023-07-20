import React, { ChangeEvent } from 'react';

import { useDispatch } from 'react-redux';

import { FormBuilderTagNames } from '@app/models/enums/formBuilder';
import { setUpdateField } from '@app/store/form-builder/actions';
import { updateField } from '@app/store/form-builder/slice';
import { contentEditableClassNames } from '@app/utils/formBuilderBlockUtils';

interface IHeaderInputBlockProps {
    field: any;
    id: any;
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
export default function HeaderInputBlock({ field, id }: IHeaderInputBlockProps) {
    const dispatch = useDispatch();
    const onChange = (event: ChangeEvent<HTMLInputElement>) => {
        dispatch(setUpdateField({ ...field, value: event.target.value }));
    };
    return <input id={id} value={field.value || ''} className={'w-full ' + contentEditableClassNames(false, field.type)} onChange={onChange} placeholder={getPlaceholder(field.type)} />;
}
