import { ChangeEvent } from 'react';

import FormBuilderInput from '@Components/FormBuilder/FormBuilderInput';
import { AlternateEmail, DateRange, LocalPhone, Numbers, ShortText } from '@mui/icons-material';
import LinkIcon from '@mui/icons-material/Link';
import { useDispatch } from 'react-redux';

import { FormBuilderTagNames } from '@app/models/enums/formBuilder';
import { addField } from '@app/store/form-builder/slice';

interface IEndAdornmentInputFieldProps {
    field: any;
    id: any;
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

export default function EndAdornmentInputField({ field, id }: IEndAdornmentInputFieldProps) {
    const dispatch = useDispatch();
    const onChange = (event: ChangeEvent<HTMLInputElement>) => {
        dispatch(addField({ ...field, properties: { ...field.properties, placeholder: event.target.value } }));
    };
    return (
        <FormBuilderInput
            onChange={onChange}
            id={id}
            value={field?.properties?.placeholder || ''}
            InputProps={{
                endAdornment: getIcon(field.tag)
            }}
        />
    );
}
