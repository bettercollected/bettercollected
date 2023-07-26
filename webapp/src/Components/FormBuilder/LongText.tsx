import { ChangeEvent, useEffect, useRef } from 'react';

import FormBuilderInput from '@Components/FormBuilder/FormBuilderInput';
import { FieldRequired } from '@Components/UI/FieldRequired';
import { Notes } from '@mui/icons-material';
import { useDispatch } from 'react-redux';

import { setUpdateField } from '@app/store/form-builder/actions';
import { selectBuilderState } from '@app/store/form-builder/selectors';
import { updateField } from '@app/store/form-builder/slice';
import { IFormFieldState } from '@app/store/form-builder/types';
import { useAppSelector } from '@app/store/hooks';

export default function LongText({ field, id, position }: { field: IFormFieldState; id: any; position: number }) {
    const dispatch = useDispatch();
    const onChange = (event: ChangeEvent<HTMLInputElement>) => {
        dispatch(setUpdateField({ ...field, properties: { ...field.properties, placeholder: event.target.value } }));
    };

    const inputRef = useRef<HTMLInputElement>(null);
    const builderState = useAppSelector(selectBuilderState);

    const activeFieldIndex = builderState.activeFieldIndex;

    useEffect(() => {
        // Focus on the first contentEditable element (title) when the page loads
        if (position !== activeFieldIndex) return;

        inputRef?.current?.focus();

        // Set the cursor position to 0 when the page loads
        // const range = document.createRange();
        //
        // if (inputRef?.current) {
        //     range.selectNodeContents(inputRef.current);
        //     range.collapse(true);
        // }
        // const selection = window.getSelection();
        // if (selection) {
        //     selection.removeAllRanges();
        //     selection.addRange(range);
        // }
    }, [position, activeFieldIndex]);

    return (
        <div className="relative w-full h-full">
            {field?.validations?.required && <FieldRequired className="top-0.5 right-1" />}
            <FormBuilderInput
                multiline
                id={id}
                inputRef={inputRef}
                onChange={onChange}
                minRows={5}
                maxRows={10}
                InputProps={{
                    endAdornment: <Notes />,
                    sx: {
                        '& .css-3fezr7-MuiInputBase-root-MuiOutlinedInput-root': {
                            padding: '4px 8px 4px 8px'
                        },
                        fontSize: '.875rem;',
                        alignItems: 'flex-start'
                    }
                }}
            />
        </div>
    );
}
