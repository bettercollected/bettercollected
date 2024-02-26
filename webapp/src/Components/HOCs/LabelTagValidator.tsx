import React, { useCallback, useEffect } from 'react';

import useBuilderTranslation from '@app/lib/hooks/use-builder-translation';
import { FormBuilderTagNames, NonInputFormBuilderTagNames } from '@app/models/enums/formBuilder';
import { setAddNewField } from '@app/store/form-builder/actions';
import { selectActiveFieldId, selectFormField, selectPreviousField } from '@app/store/form-builder/selectors';
import { IFormFieldState } from '@app/store/form-builder/types';
import { useAppAsyncDispatch, useAppSelector } from '@app/store/hooks';
import { createNewField } from '@app/utils/formBuilderBlockUtils';


interface LabelTagValidatorProps extends React.PropsWithChildren {
    position: number;
    id: string;
}

export default function LabelTagValidator({ children, position, id }: LabelTagValidatorProps) {
    const { t } = useBuilderTranslation();

    const dispatch = useAppAsyncDispatch();
    const previousField = useAppSelector(selectPreviousField(id));
    const field: IFormFieldState = useAppSelector(selectFormField(id));
    const activeFieldId = useAppSelector(selectActiveFieldId);
    const hintBox = (text: string) => {
        return <div className="bg-gray-100 p-1 rounded-sm">{text}</div>;
    };
    const validateField = (field: IFormFieldState) => {
        if (NonInputFormBuilderTagNames.includes(field.type)) return true;

        return previousField?.type === FormBuilderTagNames.LAYOUT_LABEL;
    };
    const hasMissingLabel = field ? !validateField(field) && activeFieldId === field.id : false;

    const addLabel = () => {
        const newField = createNewField(field?.position - 1, FormBuilderTagNames.LAYOUT_LABEL);
        dispatch(setAddNewField(newField)).then(() => {
            const Element = document.getElementById('item-' + newField.id);
            Element?.focus();
        });
    };

    const onKeyDownCallback = useCallback(
        (event: KeyboardEvent) => {
            if ((event.key === 'l' || event.key === 'L') && event.altKey && hasMissingLabel) {
                addLabel();
            }
        },
        [field?.position, hasMissingLabel]
    );
    useEffect(() => {
        document.addEventListener('keydown', onKeyDownCallback);

        return () => {
            document.removeEventListener('keydown', onKeyDownCallback);
        };
    }, [field?.position, activeFieldId]);

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