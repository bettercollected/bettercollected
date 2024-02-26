import { useRef } from 'react';

import AppTextField from '@Components/Common/Input/AppTextField';
import { FieldRequired } from '@Components/UI/FieldRequired';
import { AlternateEmail, DateRange, LocalPhone, Numbers, ShortText } from '@mui/icons-material';
import LinkIcon from '@mui/icons-material/Link';
import { useDispatch } from 'react-redux';

import useFormBuilderState from '@app/containers/form-builder/context';
import useUserTypingDetection from '@app/lib/hooks/use-user-typing-detection';
import useUndoRedo from '@app/lib/use-undo-redo';
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

export default function EndAdornmentInputField({ field, id, placeholder }: IEndAdornmentInputFieldProps) {
    const inputRef = useRef<HTMLInputElement>(null);
    const { setBackspaceCount } = useFormBuilderState();
    const { handleUserTypingEnd } = useUserTypingDetection();
    const { isUndoRedoInProgress } = useUndoRedo();
    const dispatch = useDispatch();
    const onChange = (event: any) => {
        if (isUndoRedoInProgress) return;
        setBackspaceCount(0);
        dispatch(setUpdateField({ ...field, properties: { ...field.properties, placeholder: event.target.value } }));
        handleUserTypingEnd();
    };

    return (
        <div className="relative w-full h-full">
            {field?.validations?.required && <FieldRequired className="top-0.5 right-1" />}
            <AppTextField
                autoFocus={false}
                onChange={onChange}
                placeholder={placeholder}
                id={id}
                value={field.properties?.placeholder || ''}
                inputRef={inputRef}
                isPlaceholder
                InputProps={{
                    endAdornment: getIcon(field.type)
                }}
            />
        </div>
    );
}