import { ChangeEvent, useRef } from 'react';

import FormBuilderInput from '@Components/FormBuilder/FormBuilderInput';
import { FieldRequired } from '@Components/UI/FieldRequired';
import { AlternateEmail, DateRange, LocalPhone, Numbers, ShortText } from '@mui/icons-material';
import LinkIcon from '@mui/icons-material/Link';
import { useDispatch } from 'react-redux';

import useFormBuilderState from '@app/containers/form-builder/context';
import { FormBuilderTagNames } from '@app/models/enums/formBuilder';
import { setUpdateField } from '@app/store/form-builder/actions';
import { IFormFieldState } from '@app/store/form-builder/types';

interface IEndAdornmentInputFieldProps {
    field: IFormFieldState;
    id: string;
    position: number;
    placeholder?: string;
}

function getIcon(type: FormBuilderTagNames) {
    switch (type) {
        case FormBuilderTagNames.INPUT_EMAIL:
            return <AlternateEmail />;
        case FormBuilderTagNames.INPUT_DATE:
            return <DateRange />;
        case FormBuilderTagNames.INPUT_SHORT_TEXT:
            return <ShortText />;
        case FormBuilderTagNames.INPUT_LINK:
            return <LinkIcon />;
        case FormBuilderTagNames.INPUT_NUMBER:
            return <Numbers />;
        case FormBuilderTagNames.INPUT_PHONE_NUMBER:
            return <LocalPhone />;
        default:
            return <></>;
    }
}

export default function EndAdornmentInputField({ field, id, position, placeholder }: IEndAdornmentInputFieldProps) {
    const inputRef = useRef<HTMLInputElement>(null);
    const dispatch = useDispatch();
    const { setBackspaceCount } = useFormBuilderState();

    const onChange = (event: ChangeEvent<HTMLInputElement>) => {
        setBackspaceCount(0);
        dispatch(setUpdateField({ ...field, properties: { ...field.properties, placeholder: event.target.value } }));
    };

    return (
        <div className="relative w-full h-full">
            {field?.validations?.required && <FieldRequired className="top-0.5 right-1" />}
            <FormBuilderInput
                autoFocus={true}
                onChange={onChange}
                placeholder={placeholder}
                id={id}
                value={field?.properties?.placeholder || ''}
                inputRef={inputRef}
                InputProps={{
                    endAdornment: getIcon(field.type)
                }}
                onFocus={(event) => {
                    inputRef?.current?.setSelectionRange(event.currentTarget.value.length, event.currentTarget.value.length);
                }}
            />
        </div>
    );
}
