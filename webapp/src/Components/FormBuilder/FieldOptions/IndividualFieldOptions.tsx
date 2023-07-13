import React from 'react';

import StepsOption from '@Components/FormBuilder/FieldOptions/StepsOption';

import { IFormFieldState } from '@app/store/form-builder/types';

interface IIndividualFieldOptionsProps {
    field: IFormFieldState;
}

export default function IndividualFieldOptions({ field }: IIndividualFieldOptionsProps) {
    return (
        <>
            <StepsOption field={field} />
        </>
    );
}
