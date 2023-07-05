import { ChangeEvent } from 'react';

import FormBuilderInput from '@Components/FormBuilder/FormBuilderInput';
import { ArrowDropDown, TrendingUpSharp } from '@mui/icons-material';
import CheckBoxOutlineBlankIcon from '@mui/icons-material/CheckBoxOutlineBlank';
import RadioButtonUncheckedIcon from '@mui/icons-material/RadioButtonUnchecked';

import { FormBuilderTagNames } from '@app/models/enums/formBuilder';

interface IStartAdornmentInputFieldProps {
    type: FormBuilderTagNames;
    value: string;
    onChange: (event: ChangeEvent<HTMLInputElement>) => void;
}

function getIcon(type: FormBuilderTagNames) {
    switch (type) {
        case FormBuilderTagNames.QUESTION_CHECKBOXES:
            return <CheckBoxOutlineBlankIcon />;
        case FormBuilderTagNames.QUESTION_MULTIPLE_CHOICE:
            return <RadioButtonUncheckedIcon />;
        case FormBuilderTagNames.QUESTION_DROPDOWN:
            return <ArrowDropDown />;
        case FormBuilderTagNames.QUESTION_RANKING:
            return <TrendingUpSharp />;
        default:
            return <></>;
    }
}

export default function StartAdornmentInputField({ type, value, onChange }: IStartAdornmentInputFieldProps) {
    return (
        <FormBuilderInput
            autoFocus={false}
            className="!w-fit !mb-0"
            value={value}
            onChange={onChange}
            placeholder="Option"
            InputProps={{
                startAdornment: getIcon(type)
            }}
        />
    );
}
