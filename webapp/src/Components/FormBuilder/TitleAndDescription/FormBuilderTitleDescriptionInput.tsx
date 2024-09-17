import React, { FormEvent } from 'react';

import CustomContentEditable from '@Components/FormBuilder/ContentEditable/CustomContentEditable';

import useBuilderTranslation from '@app/lib/hooks/use-builder-translation';
import { IBuilderTitleAndDescriptionObj } from '@app/store/form-builder/types';


interface FormBuilderTitleDescriptionInputProps {
    b: IBuilderTitleAndDescriptionObj;
    value: string;
    onChangeCallback: (event: FormEvent<HTMLElement>, b: IBuilderTitleAndDescriptionObj) => void;
    onFocusCallback: (event: React.FocusEvent<HTMLElement>, b: IBuilderTitleAndDescriptionObj) => void;
}

function FormBuilderTitleDescriptionInput({ b, value, onChangeCallback, onFocusCallback }: FormBuilderTitleDescriptionInputProps) {
    const { t } = useBuilderTranslation();
    return (
        <CustomContentEditable
            key={b.id}
            id={b.id}
            tagName={b.tagName}
            type={b.type}
            value={value}
            position={b.position}
            placeholder={t(b.placeholder)}
            className={b.className}
            onChangeCallback={(event: FormEvent<HTMLElement>) => {
                onChangeCallback(event, b);
            }}
            onFocusCallback={(event: React.FocusEvent<HTMLElement>) => {
                onFocusCallback(event, b);
            }}
        />
    );
}

export default React.memo(FormBuilderTitleDescriptionInput);