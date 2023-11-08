import React, { useEffect, useState } from 'react';

import AppTextField from '@Components/Common/Input/AppTextField';
import ConditionalListDropDown from '@Components/FormBuilder/Conditionals/ConditionalListDropDown';

import { FormBuilderTagNames, LabelFormBuilderTagNames } from '@app/models/enums/formBuilder';
import { updateConditional } from '@app/store/form-builder/actions';
import { selectFields, selectFormField } from '@app/store/form-builder/selectors';
import { Comparison, Condition, IFormFieldState } from '@app/store/form-builder/types';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { getComparisonsBasedOnFieldType } from '@app/utils/conditionalUtils';
import { getPreviousField } from '@app/utils/formBuilderBlockUtils';

const ValueNotShownComparisons = [Comparison.IS_EMPTY, Comparison.IS_NOT_EMPTY];
const TextFieldInputValueComparisons = [Comparison.STARTS_WITH, Comparison.ENDS_WITH, Comparison.IS_EQUAL, Comparison.IS_NOT_EQUAL];

const IfBlock = ({ field, condition }: { field: IFormFieldState; condition: Condition }) => {
    const formFields = useAppSelector(selectFields);

    const fields = Object.values(formFields);

    const [inputFields, setInputFields] = useState<any>([]);
    const dispatch = useAppDispatch();

    const selectedField = useAppSelector(selectFormField(condition?.field?.id || ''));

    useEffect(() => {
        const filteredFields: Array<any> = [];
        fields.forEach((field) => {
            if (field.type.includes('input_')) {
                const x: any = {
                    fieldId: field.id
                };
                const previousField = getPreviousField(fields, field);
                let text = field?.properties?.placeholder;
                if (LabelFormBuilderTagNames.includes(previousField?.type)) {
                    text = previousField?.value;
                }
                x.value = text;
                filteredFields.push(x);
            }
        });
        setInputFields(filteredFields);
    }, [formFields]);

    const onConditionFieldChange = (item: any) => {
        dispatch(
            updateConditional({
                fieldId: field.id,
                conditionalId: condition.id,
                data: { ...condition, field: { id: item.fieldId } }
            })
        );
    };

    const onComparisonChange = (item: any) => {
        dispatch(
            updateConditional({
                fieldId: field.id,
                conditionalId: condition.id,
                data: { ...condition, comparison: item.comparison }
            })
        );
    };

    const onValueChange = (event: any) => {
        dispatch(
            updateConditional({
                fieldId: field.id,
                conditionalId: condition.id,
                data: { ...condition, value: event.target.value }
            })
        );
    };

    const getInputModeForType = (type: FormBuilderTagNames) => {
        switch (type) {
            case FormBuilderTagNames.INPUT_NUMBER:
                return 'numeric';
            default:
                return 'text';
        }
    };

    return (
        <div className={'flex flex-col gap-2 p-4 rounded-lg bg-new-white-200'}>
            <h1 className={'text-pink-500 text-sm'}>IF</h1>
            <div className={'flex flex-row gap-2 '}>
                <ConditionalListDropDown
                    value={inputFields.find((item: any) => item.fieldId === condition.field?.id) || null}
                    items={inputFields}
                    labelPicker={(item: any) => {
                        return item?.value;
                    }}
                    onChange={onConditionFieldChange}
                />
                <ConditionalListDropDown
                    size={'small'}
                    value={getComparisonsBasedOnFieldType(selectedField?.type).find((item: any) => item.comparison === condition.comparison) || null}
                    onChange={onComparisonChange}
                    items={getComparisonsBasedOnFieldType(selectedField?.type)}
                />
                {condition.comparison && !ValueNotShownComparisons.includes(condition.comparison) && (
                    <>
                        {TextFieldInputValueComparisons.includes(condition.comparison) ? (
                            <>
                                <AppTextField
                                    value={condition?.value || ''}
                                    onChange={onValueChange}
                                    placeholder="Value"
                                    inputMode={getInputModeForType(selectedField?.type)}
                                    inputProps={{
                                        style: {
                                            paddingTop: 0,
                                            paddingBottom: 0,
                                            height: 42,
                                            fontSize: 16,
                                            color: 'black',
                                            fontWeight: 400,
                                            content: 'none',
                                            letterSpacing: 0
                                        }
                                    }}
                                />
                            </>
                        ) : (
                            <ConditionalListDropDown />
                        )}
                    </>
                )}
            </div>
        </div>
    );
};

export default IfBlock;
