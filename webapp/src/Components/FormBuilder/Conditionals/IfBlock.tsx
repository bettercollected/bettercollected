import React, { useEffect, useState } from 'react';

import AppTextField from '@Components/Common/Input/AppTextField';
import MenuDropdown from '@Components/Common/Navigation/MenuDropdown/MenuDropdown';
import ConditionalListDropDown from '@Components/FormBuilder/Conditionals/ConditionalListDropDown';
import ConditionalOptionsDropdown from '@Components/FormBuilder/Conditionals/ConditionalOptionsDropdown';
import { MenuItem, Select } from '@mui/material';

import { FormBuilderTagNames, LabelFormBuilderTagNames } from '@app/models/enums/formBuilder';
import { addCondition, deleteCondition, updateConditional } from '@app/store/form-builder/actions';
import { selectFields, selectFormField } from '@app/store/form-builder/selectors';
import { Comparison, Condition, IFormFieldState } from '@app/store/form-builder/types';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { getComparisonsBasedOnFieldType } from '@app/utils/conditionalUtils';
import { getPreviousField } from '@app/utils/formBuilderBlockUtils';

const TextFieldInputValueComparisons = [Comparison.STARTS_WITH, Comparison.ENDS_WITH, Comparison.IS_EQUAL, Comparison.IS_NOT_EQUAL];
const TextFieldValueFieldTypes = [FormBuilderTagNames.INPUT_SHORT_TEXT, FormBuilderTagNames.INPUT_LONG_TEXT, FormBuilderTagNames.INPUT_PHONE_NUMBER, FormBuilderTagNames.INPUT_NUMBER, FormBuilderTagNames.INPUT_EMAIL];

const SingleOptionsValueFieldTypes = [FormBuilderTagNames.INPUT_MULTIPLE_CHOICE, FormBuilderTagNames.INPUT_DROPDOWN];
const SingleOptionsValueComparisons = [Comparison.IS_EQUAL, Comparison.IS_NOT_EQUAL];

const MultipleOptionsValueFieldTypes = [FormBuilderTagNames.INPUT_CHECKBOXES, FormBuilderTagNames.INPUT_MULTISELECT];
const MultipleOptionsValueComparisons = [Comparison.CONTAINS, Comparison.DOES_NOT_CONTAIN];
const IfBlock = ({ field, condition }: { field: IFormFieldState; condition: Condition }) => {
    const formFields = useAppSelector(selectFields);

    const fields = Object.values(formFields);

    const [inputFields, setInputFields] = useState<any>([]);
    const dispatch = useAppDispatch();

    const selectedField: IFormFieldState = useAppSelector(selectFormField(condition?.field?.id || ''));

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
                data: { ...condition, field: { id: item.fieldId }, value: '' }
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

    const onTextValueChange = (event: any) => {
        dispatch(
            updateConditional({
                fieldId: field.id,
                conditionalId: condition.id,
                data: { ...condition, value: event.target.value }
            })
        );
    };

    const onOptionValueChange = (value: any) => {
        dispatch(
            updateConditional({
                fieldId: field.id,
                conditionalId: condition.id,
                data: { ...condition, value }
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

    const addNewCondition = () => {
        dispatch(addCondition(field.id));
    };
    const removeCondition = () => {
        dispatch(deleteCondition({ fieldId: field.id, conditionId: condition.id }));
    };

    return (
        <div className={'flex flex-col gap-2 '}>
            {condition?.position === 0 ? (
                <h1 className={'text-pink-500 text-sm'}>IF</h1>
            ) : (
                <div>
                    <MenuDropdown showExpandMore={condition?.position === 1} id="condition operator" className="text-pink-500" menuTitle="" menuContent={<div className="text-pink-500 capitalize text-sm">{field?.properties?.logicalOperator}</div>}>
                        <MenuItem value={'and'}>AND</MenuItem>
                        <MenuItem value={'or'}>OR</MenuItem>
                    </MenuDropdown>
                </div>
            )}
            <div className="flex justify-between items-center w-full">
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

                    {condition.comparison && SingleOptionsValueFieldTypes.includes(selectedField.type) && SingleOptionsValueComparisons.includes(condition.comparison) && (
                        <>
                            <ConditionalListDropDown value={condition?.value} onChange={onOptionValueChange} labelPicker={(value: string) => value} items={Object.values(selectedField?.properties?.choices || {}).map((choice: any) => choice.value)} />
                        </>
                    )}
                    {condition.comparison && TextFieldValueFieldTypes.includes(selectedField?.type) && TextFieldInputValueComparisons.includes(condition.comparison) && (
                        <AppTextField
                            value={condition?.value || ''}
                            onChange={onTextValueChange}
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
                    )}
                    {condition.comparison && MultipleOptionsValueFieldTypes.includes(selectedField?.type) && MultipleOptionsValueComparisons.includes(condition.comparison) && (
                        <ConditionalListDropDown
                            multiple
                            value={condition?.value && Array.isArray(condition?.value) ? condition.value : []}
                            onChange={onOptionValueChange}
                            labelPicker={(value: string) => value}
                            items={Object.values(selectedField?.properties?.choices || {}).map((choice) => choice.value)}
                        />
                    )}
                </div>
                {condition?.position === Object.keys(field?.properties?.conditions || {}).length - 1 && <ConditionalOptionsDropdown addOption={addNewCondition} removeOption={removeCondition} />}
            </div>
        </div>
    );
};

export default IfBlock;
