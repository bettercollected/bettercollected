import { StandardFormFieldDto } from '@app/models/dtos/form';
import { cn } from '@app/shadcn/util/lib';
import { useAtomValue } from 'jotai';

import { activeFieldAtom } from '@app/store/jotai/active-builder-component';
import { useBuilderActions } from '@app/store/jotai/field-selectors';
import { useFormState } from '@app/store/jotai/form';
import MatrixField from './matrix';

export default function MatrixFieldBuilderWrapper({ field }: { field: StandardFormFieldDto }) {
    const { theme } = useFormState();
    const { addRow, addColumn } = useBuilderActions();
    const activeField = useAtomValue(activeFieldAtom);
    return (
        <div className="flex flex-col gap-4">
            <div style={{ color: theme?.secondary }} className={cn(' flex w-full  justify-end ', field.id !== activeField?.id && 'invisible')}>
                <button type="button" className="cursor-pointer rounded focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#123FC9]" onClick={() => addColumn()}>
                    Add Column
                </button>
            </div>
            <MatrixField field={field} disabled />
            <div style={{ color: theme?.secondary }} className={cn('text-brand-500 flex w-full justify-start ', field.id !== activeField?.id && 'invisible')}>
                <button type="button" className="cursor-pointer rounded focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#123FC9]" onClick={() => addRow()}>
                    Add Row
                </button>
            </div>
        </div>
    );
}
