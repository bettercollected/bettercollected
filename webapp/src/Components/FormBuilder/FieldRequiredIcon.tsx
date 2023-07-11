import { setFieldRequired } from '@app/store/form-builder/slice';
import { FormFieldState } from '@app/store/form-builder/types';
import { useAppDispatch } from '@app/store/hooks';

interface IFieldRequiredIconProps {
    field: FormFieldState;
}

export default function FieldRequiredIcon({ field }: IFieldRequiredIconProps) {
    const dispatch = useAppDispatch();
    const onClick = () => {
        dispatch(setFieldRequired({ fieldId: field?.id, required: false }));
    };
    if (field?.validations?.required)
        return (
            <>
                <div className="absolute -top-2 cursor-pointer  rounded-full" onClick={onClick}>
                    <span className="!w-4 text-center flex items-center justify-center pt-1.5 text-xl font-bold rounded-full !h-4 relative -left-2  bg-gray-300 px-0.5  z-[35003]">*</span>
                </div>
            </>
        );

    return <></>;
}
