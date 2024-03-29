import React from 'react';

import IfBlock from '@Components/FormBuilder/Conditionals/IfBlock';
import ThenBlock from '@Components/FormBuilder/Conditionals/ThenBLock';

import { ConditionalActions, IFormFieldState } from '@app/store/form-builder/types';

interface IConditionalFieldProps {
    field: IFormFieldState;
    id: string;
}

export default function Conditional({ field, id }: IConditionalFieldProps) {
    return (
        <div tabIndex={0} id={id} className="relative flex flex-col gap-4 p-4 border-2 border-dashed border-black-300 outline-none rounded-lg w-full lg:min-w-[800px]">
            <div className="p-2 md:p-4 rounded-lg bg-new-white-200">
                {Object.values(field?.properties?.conditions || {}).map((condition, index: number) => (
                    <IfBlock field={field} key={(condition?.id || '') + index} condition={condition} />
                ))}
            </div>
            <div className="p-2 md:p-4 rounded-lg bg-new-white-200 ">
                {Object.values(field?.properties?.actions || {}).map((action: ConditionalActions, index: number) => (
                    <ThenBlock field={field} action={action} key={action?.id || '' + index} />
                ))}
            </div>
        </div>
    );
}