import { ChangeEvent, ChangeEventHandler, FocusEventHandler, useRef } from 'react';

import FormBuilderInput from '@Components/FormBuilder/FormBuilderInput';
import { ArrowDropDown, TrendingUpSharp } from '@mui/icons-material';
import CheckBoxOutlineBlankIcon from '@mui/icons-material/CheckBoxOutlineBlank';
import RadioButtonUncheckedIcon from '@mui/icons-material/RadioButtonUnchecked';

import useFormBuilderState from '@app/containers/form-builder/context';
import useBuilderTranslation from '@app/lib/hooks/use-builder-translation';
import { FormBuilderTagNames } from '@app/models/enums/formBuilder';


interface IStartAdornmentInputFieldProps {
    type: FormBuilderTagNames;
    value: string;
    id: string;
    focus?: boolean;
    onChangeCallback: ChangeEventHandler<HTMLInputElement>;
    onFocusCallback?: FocusEventHandler<HTMLInputElement | HTMLTextAreaElement>;
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

export default function StartAdornmentInputField({ type, value, id, onChangeCallback, onFocusCallback }: IStartAdornmentInputFieldProps) {
    const { setBackspaceCount } = useFormBuilderState();
    const inputRef = useRef(null);
    const { t } = useBuilderTranslation();

    const onChange = (event: ChangeEvent<HTMLInputElement>) => {
        setBackspaceCount(0);
        onChangeCallback(event);
    };

    const onFocus = (event: any) => {
        onFocusCallback && onFocusCallback(event);
    };

    return (
        <FormBuilderInput
            autoFocus={false}
            id={id}
            inputRef={inputRef}
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