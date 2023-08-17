import { ChangeEvent, useEffect, useRef } from 'react';

import FormBuilderInput from '@Components/FormBuilder/FormBuilderInput';
import { FieldRequired } from '@Components/UI/FieldRequired';
import { Notes } from '@mui/icons-material';
import { useDispatch } from 'react-redux';

import useFormBuilderState from '@app/containers/form-builder/context';
import { setUpdateField } from '@app/store/form-builder/actions';
import { selectBuilderState } from '@app/store/form-builder/selectors';
import { IFormFieldState } from '@app/store/form-builder/types';
import { useAppSelector } from '@app/store/hooks';

export default function LongText({ field, id, position }: { field: IFormFieldState; id: any; position: number }) {
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
