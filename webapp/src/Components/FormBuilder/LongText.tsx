import { ChangeEvent } from 'react';

import FormBuilderInput from '@Components/FormBuilder/FormBuilderInput';
import { Notes } from '@mui/icons-material';
import { useDispatch } from 'react-redux';

import { addField } from '@app/store/form-builder/slice';
import { FormFieldState } from '@app/store/form-builder/types';

export default function LongText({ field }: { field: FormFieldState }) {
    const dispatch = useDispatch();
    const onChange = (event: ChangeEvent<HTMLInputElement>) => {
        dispatch(addField({ ...field, properties: { ...field.properties, placeholder: event.target.value } }));
    };

    return (
        <FormBuilderInput
            multiline
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
    );
}
