import { StandardFormFieldDto } from '@app/models/dtos/form';
import MatrixField from './Matrix';
import useFormFieldsAtom from '@app/store/jotai/fieldSelector';
import { cn } from '@app/shadcn/util/lib';

export default function MatrixFieldBuilderWrapper({ field }: { field: StandardFormFieldDto }) {
    const { addRow, addColumn, activeField } = useFormFieldsAtom();
    return (
        <div className="flex flex-col gap-4">
            <div className={cn('text-brand-500 flex w-full  justify-end ', field.id !== activeField?.id && 'invisible')}>
                <span
                    className="cursor-pointer"
                    onClick={() => {
                        addColumn();
                    }}
                >
                    Add Column
                </span>
            </div>
            <MatrixField field={field} disabled />
            <div
                className={cn('text-brand-500 flex w-full cursor-pointer justify-start ', field.id !== activeField?.id && 'invisible')}
                onClick={() => {
                    addRow();
                }}
            >
                Add Row
            </div>
        </div>
    );
}
