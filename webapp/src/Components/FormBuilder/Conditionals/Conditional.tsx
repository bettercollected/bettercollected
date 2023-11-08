import React, { Fragment, useEffect, useState } from 'react';

import _ from 'lodash';

import IfBlock from '@Components/FormBuilder/Conditionals/IfBlock';
import ThenBlock from '@Components/FormBuilder/Conditionals/ThenBLock';
import { FieldRequired } from '@Components/UI/FieldRequired';
import { Combobox, Listbox } from '@headlessui/react';
import { Star, StarBorder } from '@mui/icons-material';

import { ArrowDown } from '@app/components/icons/arrow-down';
import { FormBuilderConditionalComparison } from '@app/models/dtos/formBuilder';
import { LabelFormBuilderTagNames, NonInputFormBuilderTagNames } from '@app/models/enums/formBuilder';
import { selectFields } from '@app/store/form-builder/selectors';
import { ConditionalActions, IFormFieldState } from '@app/store/form-builder/types';
import { useAppSelector } from '@app/store/hooks';
import { getPreviousField } from '@app/utils/formBuilderBlockUtils';

interface IConditionalFieldProps {
    field: IFormFieldState;
    id: string;
}

export default function Conditional({ field, id }: IConditionalFieldProps) {
    return (
        <div tabIndex={0} id={id} className="flex flex-col gap-4 mt-6 w-fit p-4 border-2 border-dashed border-black-300 outline-none rounded-lg">
            {Object.values(field?.properties?.conditions || {}).map((condition) => (
                <IfBlock field={field} key={condition?.id} />
            ))}
            {Object.values(field?.properties?.actions || {}).map((action: ConditionalActions) => (
                <ThenBlock field={field} action={action} key={action?.id} />
            ))}
        </div>
    );
}
