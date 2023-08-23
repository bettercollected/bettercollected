import React, {useCallback, useEffect} from 'react';

import {FormBuilderTagNames, NonInputFormBuilderTagNames} from '@app/models/enums/formBuilder';
import {setAddNewField} from '@app/store/form-builder/actions';
import {selectBuilderState} from '@app/store/form-builder/selectors';
import {IFormFieldState} from '@app/store/form-builder/types';
import {useAppDispatch, useAppSelector} from '@app/store/hooks';
import {createNewField} from '@app/utils/formBuilderBlockUtils';

interface LabelTagValidatorProps extends React.PropsWithChildren {
    position: number;
}

export default function LabelTagValidator({children, position}: LabelTagValidatorProps) {
    const builderState = useAppSelector(selectBuilderState);

    const dispatch = useAppDispatch();
    const hintBox = (text: string) => {
        return <div className="bg-gray-100 p-1 rounded-sm">{text}</div>;
    };
    const validateField = useCallback(
        (field: IFormFieldState) => {
            if (NonInputFormBuilderTagNames.includes(field.type)) return true;

            const previousField: any = Object.values(builderState.fields)[field.position - 1];
            return previousField?.type === FormBuilderTagNames.LAYOUT_LABEL;
        },
        [builderState.fields]
    );

    const field = builderState.fields[builderState.activeFieldId];
    const hasMissingLabel = field ? !validateField(field) && field.position === position : false;

    const onKeyDownCallback = useCallback(
        (event: KeyboardEvent) => {
            if ((event.key === 'l' || event.key === 'L') && event.altKey && hasMissingLabel) {
                dispatch(setAddNewField(createNewField(builderState.activeFieldIndex - 1, FormBuilderTagNames.LAYOUT_LABEL)));
            }
        },
        [builderState.activeFieldIndex, dispatch, hasMissingLabel]
    );
    useEffect(() => {
        document.addEventListener('keydown', onKeyDownCallback);

        return () => {
            document.removeEventListener('keydown', onKeyDownCallback);
        };
    }, [onKeyDownCallback]);

    return (
        <div id={`label-tag-validator-${position}`} className="relative group">
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
