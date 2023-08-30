import { ChangeEvent, useEffect, useMemo, useRef, useState } from 'react';

import { debounce } from 'lodash';

import FormBuilderInput from '@Components/FormBuilder/FormBuilderInput';
import { FieldRequired } from '@Components/UI/FieldRequired';
import { Notes } from '@mui/icons-material';
import { useDispatch } from 'react-redux';

import useFormBuilderState from '@app/containers/form-builder/context';
import useUserTypingDetection from '@app/lib/hooks/use-user-typing-detection';
import useUndoRedo from '@app/lib/use-undo-redo';
import { setUpdateField } from '@app/store/form-builder/actions';
import { selectBuilderState } from '@app/store/form-builder/selectors';
import { IFormFieldState } from '@app/store/form-builder/types';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';

export default function LongText({ field, id, position }: { field: IFormFieldState; id: any; position: number }) {
    const { setBackspaceCount } = useFormBuilderState();
    const dispatch = useAppDispatch();
    const { handleUserTypingEnd } = useUserTypingDetection();
    const { isUndoRedoInProgress } = useUndoRedo();

    const onChange = (event: any) => {
        if (isUndoRedoInProgress) return;
        setBackspaceCount(0);
        dispatch(setUpdateField({ ...field, properties: { ...field.properties, placeholder: event.target.value } }));
        handleUserTypingEnd();
    };

    return (
        <div className="relative w-full h-full">
            {field?.validations?.required && <FieldRequired className="top-0.5 right-1" />}
            <FormBuilderInput
                multiline
                autoFocus={false}
                id={id}
                value={field?.properties?.placeholder || ''}
                placeholder={field?.properties?.placeholder || ''}
                onChange={onChange}
                inputMode="text"
                minRows={10}
                maxRows={20}
                InputProps={{
                    endAdornment: <Notes />,
                    sx: {
                        // '& .css-3fezr7-MuiInputBase-root-MuiOutlinedInput-root': {
                        //     padding: '4px 8px 4px 8px'
                        // },
                        fontSize: '.875rem;',
                        alignItems: 'flex-start'
                    }
                }}
            />
        </div>
    );
}
