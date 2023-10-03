import React, { useCallback, useEffect } from 'react';

import useBuilderTranslation from '@app/lib/hooks/use-builder-translation';
import { FormBuilderTagNames, NonInputFormBuilderTagNames } from '@app/models/enums/formBuilder';
import { setAddNewField } from '@app/store/form-builder/actions';
import { selectBuilderState } from '@app/store/form-builder/selectors';
import { IFormFieldState } from '@app/store/form-builder/types';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { createNewField } from '@app/utils/formBuilderBlockUtils';

interface LabelTagValidatorProps extends React.PropsWithChildren {
    position: number;
}

export default function LabelTagValidator({ children, position }: LabelTagValidatorProps) {
    const builderState = useAppSelector(selectBuilderState);

    const { t } = useBuilderTranslation();

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

    const addLabel = () => {
        dispatch(setAddNewField(createNewField(builderState.activeFieldIndex - 1, FormBuilderTagNames.LAYOUT_LABEL)));
    };

    const onKeyDownCallback = useCallback(
        (event: KeyboardEvent) => {
            if ((event.key === 'l' || event.key === 'L') && event.altKey && hasMissingLabel) {
                addLabel();
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
        <div id={`label-tag-validator-${position}`} className="group">
            {children}
            {hasMissingLabel && (
                <div className=" min-w-fit absolute div-left-to-parent-right top-2 hidden xl:block">
                    <div className="flex space-x-2 items-center text-xs font-medium text-gray-400">
                        <div className="text-sm p-1 cursor-pointer hover:bg-black-100 rounded min-w-fit" onClick={addLabel}>
                            {t('COMPONENTS.ACTIONS.ADD_LABEL')}
                        </div>
                        {hintBox('Alt')}
                        {hintBox('+')}
                        {hintBox('L')}
                    </div>
                </div>
            )}
        </div>
    );
}
