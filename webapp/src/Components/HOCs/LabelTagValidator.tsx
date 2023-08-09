import React, { useCallback, useEffect, useState } from 'react';

import { FormBuilderTagNames } from '@app/models/enums/formBuilder';
import { selectBuilderState } from '@app/store/form-builder/selectors';
import { IFormFieldState } from '@app/store/form-builder/types';
import { useAppSelector } from '@app/store/hooks';

interface LabelTagValidatorProps extends React.PropsWithChildren {
    position: number;
}

export default function LabelTagValidator({ children, position }: LabelTagValidatorProps) {
    const builderState = useAppSelector(selectBuilderState);

    const hintBox = (text: string) => {
        return <div className="bg-gray-100 p-1 rounded-sm">{text}</div>;
    };
    const validateField = useCallback(
        (field: IFormFieldState) => {
            if (field.type === FormBuilderTagNames.LAYOUT_LABEL) return true;

            const previousField = Object.values(builderState.fields)[field.position - 1];
            return previousField?.type === FormBuilderTagNames.LAYOUT_LABEL;
        },
        [builderState.fields]
    );

    const field = builderState.fields[builderState.activeFieldId];
    const hasMissingLabel = field ? !validateField(field) && field.position === position : false;

    return (
        <div className="relative group">
            {children}
            {hasMissingLabel && (
                <div className="absolute -right-40 top-1/4 ">
                    <div className="flex space-x-2 items-center text-xs font-medium text-gray-400">
                        <div className="text-sm">Add label</div>
                        {hintBox('Alt')}
                        {hintBox('+')}
                        {hintBox('L')}
                    </div>
                </div>
            )}
        </div>
    );
}
