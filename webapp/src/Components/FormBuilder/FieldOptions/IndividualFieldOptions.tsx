import React from 'react';

import StepsOption from '@Components/FormBuilder/FieldOptions/StepsOption';

import { FormFieldState } from '@app/store/form-builder/types';

interface IIndividualFieldOptionsProps {
    field: FormFieldState;
}

export default function IndividualFieldOptions({ field }: IIndividualFieldOptionsProps) {
    return (
        <>
            <StepsOption field={field} />
        </>
    );
}
