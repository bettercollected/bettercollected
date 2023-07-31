import { ChangeEvent, FocusEventHandler } from 'react';

import FormBuilderInput from '@Components/FormBuilder/FormBuilderInput';
import { ArrowDropDown, TrendingUpSharp } from '@mui/icons-material';
import CheckBoxOutlineBlankIcon from '@mui/icons-material/CheckBoxOutlineBlank';
import RadioButtonUncheckedIcon from '@mui/icons-material/RadioButtonUnchecked';

import useBuilderTranslation from '@app/lib/hooks/use-builder-translation';
import { FormBuilderTagNames } from '@app/models/enums/formBuilder';

interface IStartAdornmentInputFieldProps {
    type: FormBuilderTagNames;
    value: string;
    id: any;
    onChange: (event: ChangeEvent<HTMLInputElement>) => void;
    onFocus?: FocusEventHandler<HTMLInputElement | HTMLTextAreaElement>;
}

function getIcon(type: FormBuilderTagNames) {
    switch (type) {
        case FormBuilderTagNames.INPUT_CHECKBOXES:
            return <CheckBoxOutlineBlankIcon />;
        case FormBuilderTagNames.INPUT_MULTIPLE_CHOICE:
            return <RadioButtonUncheckedIcon />;
        case FormBuilderTagNames.INPUT_DROPDOWN:
            return <ArrowDropDown />;
        case FormBuilderTagNames.INPUT_RANKING:
            return <TrendingUpSharp />;
        default:
            return <></>;
    }
}

export default function StartAdornmentInputField({ type, value, id, onChange, onFocus }: IStartAdornmentInputFieldProps) {
    const { t } = useBuilderTranslation();
    return (
        <FormBuilderInput
            autoFocus={false}
            id={id}
            className="!w-fit !mb-0"
            value={value}
            variant="standard"
            onChange={onChange}
            onFocus={onFocus}
            inputProps={{
                style: {
                    paddingTop: 0,
                    paddingBottom: 0,
                    height: 40,
                    fontSize: 14,
                    fontWeight: 400,
                    color: 'black',
                    content: 'none',
                    letterSpacing: 1,
                    outline: 'none',
                    border: 'none'
                }
            }}
            placeholder={t('COMPONENTS.INPUT.OPTION')}
            InputProps={{
                startAdornment: <div className="text-gray-400"> {getIcon(type)}</div>
            }}
        />
    );
}
