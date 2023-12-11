import { useState } from 'react';

import AppTextField from '@Components/Common/Input/AppTextField';
import AppButton from '@Components/Common/Input/Button/AppButton';
import { ButtonSize, ButtonVariant } from '@Components/Common/Input/Button/AppButtonProps';
import HeaderModalWrapper from '@Components/Modals/HeaderModalWrapper';
import { toast } from 'react-toastify';

import { useModal } from '@app/components/modal-views/context';
import { useAddActionToFormMutation } from '@app/store/api-actions-api';
import { setForm } from '@app/store/forms/slice';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';

export default function AddActionToFormModal({ action, form, ...props }: any) {
    const { closeModal } = useModal();
    const [addActionToForm] = useAddActionToFormMutation();

    const [parameters, setParameters] = useState<any>({});
    const workspace = useAppSelector(selectWorkspace);
    const dispatch = useAppDispatch();

    const [error, setError] = useState(false);
    const onAddIntegration = async () => {
        let error = false;
        action?.parameters?.forEach((parameter: any) => {
            if (parameter.required && !parameters[parameter?.name]) {
                error = true;
            }
        });

        const overridingParams: Array<any> = [];
        Object.keys(parameters).map((paramName: string) => {
            overridingParams.push({
                name: paramName,
                value: parameters[paramName]
            });
        });

        const response: any = await addActionToForm({
            workspaceId: workspace.id,
            formId: form.formId,
            body: {
                action_id: action.id,
                trigger: 'on_submit',
                parameters: overridingParams
            }
        });
        if (response?.data) {
            dispatch(setForm({ ...form, actions: response?.data }));
            toast('Added', { type: 'success' });
            closeModal();
        } else if (response?.error) {
            toast('Error', { type: 'error' });
        }
        setError(error);
    };
    return (
        <HeaderModalWrapper headerTitle="Add integration to form">
            <div className="flex flex-col gap-2">
                <div className="h4-new">
                    Adding {action?.title || 'Untitled'} to the form {form?.title || 'Untitled'}
                </div>
                <div className="text-black-800">Params required to add action:</div>
                {action?.parameters?.map((parameter: any, index: number) =>
                    parameter?.required ? (
                        <div key={index}>
                            <div className="flex w-full items-center gap-2">
                                <div className="text-sm font-bold">{parameter.name}</div>
                                <div>
                                    <AppTextField
                                        onChange={(event) => {
                                            setParameters({ ...parameters, [parameter.name]: event.target.value });
                                        }}
                                    />
                                </div>
                            </div>
                        </div>
                    ) : (
                        <div key={index}></div>
                    )
                )}
                {error && <div className="text-red-500 text-sm ">Please fill in all required parameters.</div>}
                <AppButton variant={ButtonVariant.Primary} size={ButtonSize.Medium} onClick={onAddIntegration}>
                    Add Integration
                </AppButton>
            </div>
        </HeaderModalWrapper>
    );
}
