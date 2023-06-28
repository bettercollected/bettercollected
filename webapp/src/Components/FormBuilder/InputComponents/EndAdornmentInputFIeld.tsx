import FormBuilderInput from '@Components/FormBuilder/InputComponents/FormBuilderInput';
import { AlternateEmail, DateRange, LocalPhone, ShortText } from '@mui/icons-material';
import LinkIcon from '@mui/icons-material/Link';

import { TagIcon } from '@app/components/icons/tag-icon';

interface IEndAdornmentInputFieldProps {
    type: 'email' | 'date' | 'short_text' | 'link' | 'number' | 'phone_number';
}

function getIcon(type: string) {
    switch (type) {
        case 'email':
            return <AlternateEmail />;
        case 'date':
            return <DateRange />;
        case 'short_text':
            return <ShortText />;
        case 'link':
            return <LinkIcon />;
        case 'number':
            return <TagIcon />;
        case 'phone_number':
            return <LocalPhone />;

        default:
            return <></>;
    }
}

export default function EndAdornmentInputField({ type }: IEndAdornmentInputFieldProps) {
    return (
        <FormBuilderInput
            InputProps={{
                endAdornment: getIcon(type)
            }}
        />
    );
}
