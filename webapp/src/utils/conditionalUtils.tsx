import _ from 'lodash';

import LongTextIcon from '@Components/Common/Icons/FormBuilder/LongTextIcon';
import { AlternateEmail, ArrowDropDown, DateRange, LocalPhone, Numbers, ShortText, TrendingUpSharp } from '@mui/icons-material';
import CheckBoxOutlineBlankIcon from '@mui/icons-material/CheckBoxOutlineBlank';
import LinkIcon from '@mui/icons-material/Link';
import RadioButtonUncheckedIcon from '@mui/icons-material/RadioButtonUnchecked';

import { FormBuilderTagNames, LabelFormBuilderTagNames } from '@app/models/enums/formBuilder';
import { ActionType, Comparison, IFormFieldState } from '@app/store/form-builder/types';
import { convertPlaceholderToDisplayValue } from '@app/utils/formBuilderBlockUtils';

export function getComparisonText(comparison: Comparison): string {
    switch (comparison) {
        case Comparison.CONTAINS:
            return 'contains';
        case Comparison.DOES_NOT_CONTAIN:
            return 'does not contain';
        case Comparison.IS_EQUAL:
            return 'is equal to';
        case Comparison.IS_NOT_EQUAL:
            return 'is not equal to';
        case Comparison.STARTS_WITH:
            return 'starts with';
        case Comparison.ENDS_WITH:
            return 'ends with';
        case Comparison.IS_EMPTY:
            return 'is empty';
        case Comparison.IS_NOT_EMPTY:
            return 'is not empty';
        case Comparison.GREATER_THAN:
            return 'is greater than';
        case Comparison.LESS_THAN:
            return 'is less than';
        case Comparison.GREATER_THAN_EQUAL:
            return 'is greater than or equal to';
        case Comparison.LESS_THAN_EQUAL:
            return 'is less than or equal to';
        default:
            return 'Unknown comparison type';
    }
}

export function getComparisonsBasedOnFieldType(type?: FormBuilderTagNames) {
    if (!type) return [];
    const comparisons = [
        { comparison: Comparison.IS_EMPTY, value: 'Is Empty' },
        { comparison: Comparison.IS_NOT_EMPTY, value: 'Is Not Empty' }
    ];
    switch (type) {
        case FormBuilderTagNames.INPUT_SHORT_TEXT:
        case FormBuilderTagNames.INPUT_LONG_TEXT:
        case FormBuilderTagNames.INPUT_PHONE_NUMBER:
        case FormBuilderTagNames.INPUT_EMAIL:
        case FormBuilderTagNames.INPUT_LINK:
            comparisons.push(
                ...[
                    { comparison: Comparison.IS_EQUAL, value: 'Is Equal' },
                    { comparison: Comparison.IS_NOT_EQUAL, value: 'Is Not Equal' },
                    { comparison: Comparison.STARTS_WITH, value: 'Starts With' },
                    { comparison: Comparison.ENDS_WITH, value: 'Ends With' }
                ]
            );
            break;
        case FormBuilderTagNames.INPUT_MULTIPLE_CHOICE:
        case FormBuilderTagNames.INPUT_DROPDOWN:
            comparisons.push(
                ...[
                    { comparison: Comparison.IS_EQUAL, value: 'Is Equal' },
                    { comparison: Comparison.IS_NOT_EQUAL, value: 'Is Not Equal' }
                ]
            );
            break;

        case FormBuilderTagNames.INPUT_MULTISELECT:
        case FormBuilderTagNames.INPUT_CHECKBOXES:
            comparisons.push(
                ...[
                    { comparison: Comparison.CONTAINS, value: 'Contains' },
                    { comparison: Comparison.DOES_NOT_CONTAIN, value: 'Does Not Contain' }
                ]
            );
            break;
        case FormBuilderTagNames.INPUT_NUMBER:
        case FormBuilderTagNames.INPUT_DATE:
        case FormBuilderTagNames.INPUT_RATING:
            comparisons.push(
                ...[
                    { comparison: Comparison.IS_EQUAL, value: 'Is Equal' },
                    { comparison: Comparison.IS_NOT_EQUAL, value: 'Is Not Equal' },
                    { comparison: Comparison.GREATER_THAN, value: 'Greater Than' },
                    { comparison: Comparison.LESS_THAN, value: 'Less Than' },
                    { comparison: Comparison.GREATER_THAN_EQUAL, value: 'Greater Than Equal' },
                    { comparison: Comparison.LESS_THAN_EQUAL, value: 'Less Than Equal' }
                ]
            );
            break;
        case FormBuilderTagNames.INPUT_FILE_UPLOAD:
        default:
            break;
    }
    return comparisons;
}

const ShowAllFieldsActionType = [ActionType.HIDE_FIELDS, ActionType.SHOW_FIELDS];

export const checkShowAllFields = (actionType: ActionType) => {
    return ShowAllFieldsActionType.includes(actionType);
};

export const convertFieldForConditionalDropDownState = (field: IFormFieldState, fields: Array<IFormFieldState>, id?: string) => {
    let text = '';
    const x: any = {
        fieldId: id ? id : field.id
    };
    if (LabelFormBuilderTagNames.includes(field?.type) && field?.value) {
        text = field?.value;
    } else if (!LabelFormBuilderTagNames.includes(field?.type) && field?.properties?.placeholder) {
        text = field?.properties?.placeholder;
    } else {
        text = _.startCase(field?.type.split('_').join(' '));
    }
    x.value = convertPlaceholderToDisplayValue(fields, text);
    x.fieldType = field.type;
    return x;
};

export const getIconForFieldType = (type: FormBuilderTagNames) => {
    switch (type) {
        case FormBuilderTagNames.LAYOUT_LABEL:
            return <div className="w-6 h-6 text-xl flex justify-center font-bold">L</div>;
        case FormBuilderTagNames.LAYOUT_HEADER1:
            return <div className="w-6 h-6 text-xl flex justify-center font-bold">H1</div>;
        case FormBuilderTagNames.LAYOUT_HEADER2:
            return <div className="w-6 h-6 text-xl flex justify-center font-bold">H2</div>;
        case FormBuilderTagNames.LAYOUT_HEADER3:
            return <div className="w-6 h-6 text-xl flex justify-center font-bold">H3</div>;
        case FormBuilderTagNames.LAYOUT_HEADER4:
            return <div className="w-6 h-6 text-xl flex justify-center font-bold">H4</div>;
        case FormBuilderTagNames.INPUT_EMAIL:
            return <AlternateEmail />;
        case FormBuilderTagNames.INPUT_DATE:
            return <DateRange />;
        case FormBuilderTagNames.INPUT_SHORT_TEXT:
            return <ShortText />;
        case FormBuilderTagNames.INPUT_LONG_TEXT:
            return <LongTextIcon />;
        case FormBuilderTagNames.INPUT_LINK:
            return <LinkIcon />;
        case FormBuilderTagNames.INPUT_NUMBER:
            return <Numbers />;
        case FormBuilderTagNames.INPUT_PHONE_NUMBER:
            return <LocalPhone />;
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
};
