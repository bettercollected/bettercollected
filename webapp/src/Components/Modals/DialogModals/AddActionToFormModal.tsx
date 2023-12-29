import {useEffect, useState} from 'react';

import AppTextField from '@Components/Common/Input/AppTextField';
import AppButton from '@Components/Common/Input/Button/AppButton';
import {ButtonSize, ButtonVariant} from '@Components/Common/Input/Button/AppButtonProps';
import HeaderModalWrapper from '@Components/Modals/HeaderModalWrapper';
import {toast} from 'react-toastify';

import {useModal} from '@app/components/modal-views/context';
import {useAddActionToFormMutation} from '@app/store/api-actions-api';
import {setForm} from '@app/store/forms/slice';
import {useAppDispatch, useAppSelector} from '@app/store/hooks';
import {selectWorkspace} from '@app/store/workspaces/slice';
import {useRouter} from "next/router";
import {selectAuth} from "@app/store/auth/slice";

export default function AddActionToFormModal({action, form, ...props}: any) {
    const {closeModal} = useModal();
    const [addActionToForm] = useAddActionToFormMutation();

    const [parameters, setParameters] = useState<any>({});
    const workspace = useAppSelector(selectWorkspace);
    const router = useRouter()
    const [error, setError] = useState(false);

    const user = useAppSelector(selectAuth)

    useEffect(() => {
        if (action.name === "creator_copy_mail") {
            setParameters({["Receiving Mail Address"]: user.email})
        }
    }, [action])
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
            router.push(router.asPath)
            toast('Added', {type: 'success'});
            closeModal();
        } else if (response?.error) {
            toast('Error', {type: 'error'});
        }
        setError(error);
    };
    return (
        <HeaderModalWrapper headerTitle="Add integration to form">
            <div className="flex flex-col md:min-w-[400px]">
                <div className="h4-new">
                    Adding {action?.title || 'Untitled'} to the form {form?.title || 'Untitled'}
                </div>
                {
                    action?.parameters?.filter((param: any) => param.required).length > 0 && <>
                        <div className="text-black-800 w-full">Params required to add action:</div>
                        {action?.parameters?.map((parameter: any, index: number) =>
                            parameter?.required ? (
                                <div key={index} className="flex flex-col mt-3  w-full items-start gap-2">
                                    <div className="text-sm font-bold">{parameter.name}</div>
                                    <AppTextField className="w-full"
                                                  value={parameters[parameter.name]}
                                                  onChange={(event) => {
                                                      setParameters({...parameters, [parameter.name]: event.target.value});
                                                  }}
                                    />
                                </div>
                            ) : (
                                <div key={index}></div>
                            )
                        )}
                        {error && <div className="text-red-500 text-sm ">Please fill in all required parameters.</div>}
                    </>
                }

                <AppButton className="mt-4" variant={ButtonVariant.Primary} size={ButtonSize.Medium}
                           onClick={onAddIntegration}>
                    Add Integration
                </AppButton>
            </div>
        </HeaderModalWrapper>
    );
}
