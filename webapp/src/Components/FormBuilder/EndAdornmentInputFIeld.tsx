import { ChangeEvent, useEffect, useRef } from 'react';

import FormBuilderInput from '@Components/FormBuilder/FormBuilderInput';
import { AlternateEmail, DateRange, LocalPhone, Numbers, ShortText } from '@mui/icons-material';
import LinkIcon from '@mui/icons-material/Link';
import { value } from 'dom7';
import { useDispatch } from 'react-redux';

import { FormBuilderTagNames } from '@app/models/enums/formBuilder';
import { setUpdateField } from '@app/store/form-builder/actions';
import { selectBuilderState } from '@app/store/form-builder/selectors';
import { updateField } from '@app/store/form-builder/slice';
import { useAppSelector } from '@app/store/hooks';

interface IEndAdornmentInputFieldProps {
    field: any;
    id: any;
    position: number;
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

export default function EndAdornmentInputField({ field, id, position }: IEndAdornmentInputFieldProps) {
    const inputRef = useRef<HTMLInputElement>(null);
    const dispatch = useDispatch();
    const onChange = (event: ChangeEvent<HTMLInputElement>) => {
        dispatch(setUpdateField({ ...field, properties: { ...field.properties, placeholder: event.target.value } }));
    };

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

    return (
        <FormBuilderInput
            onChange={onChange}
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
    );
}
