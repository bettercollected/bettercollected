import FormBuilderInput from '@Components/FormBuilder/InputComponents/FormBuilderInput';
import { ArrowDropDown, TrendingUpSharp } from '@mui/icons-material';
import CheckBoxOutlineBlankIcon from '@mui/icons-material/CheckBoxOutlineBlank';
import RadioButtonUncheckedIcon from '@mui/icons-material/RadioButtonUnchecked';

interface IStartAdornmentInputFieldProps {
    type: 'checkbox' | 'choice' | 'dropdown' | 'ranking';
}

function getIcon(type: string) {
    switch (type) {
        case 'checkbox':
            return <CheckBoxOutlineBlankIcon />;
        case 'choice':
            return <RadioButtonUncheckedIcon />;
        case 'dropdown':
            return <ArrowDropDown />;
        case 'ranking':
            return <TrendingUpSharp />;
        default:
            return <></>;
    }
}

export default function StartAdornmentInputField({ type }: IStartAdornmentInputFieldProps) {
    return (
        <FormBuilderInput
            className="w-fit"
            InputProps={{
                startAdornment: getIcon(type)
            }}
        />
    );
}
