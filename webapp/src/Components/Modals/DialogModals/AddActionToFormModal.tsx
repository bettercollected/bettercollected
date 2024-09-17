import { useEffect, useState } from 'react';

import { useRouter } from 'next/router';

import AppTextField from '@Components/Common/Input/AppTextField';
import AppButton from '@Components/Common/Input/Button/AppButton';
import { ButtonSize, ButtonVariant } from '@Components/Common/Input/Button/AppButtonProps';
import HeaderModalWrapper from '@Components/Modals/ModalWrappers/HeaderModalWrapper';
import { toast } from 'react-toastify';

import { useModal } from '@app/Components/modal-views/context';
import { useAddActionToFormMutation } from '@app/store/api-actions-api';
import { selectAuth } from '@app/store/auth/slice';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';

export default function AddActionToFormModal({ action, form, ...props }: any) {
    const { closeModal } = useModal();
    const [addActionToForm, { isLoading }] = useAddActionToFormMutation();
    const [fetchOauthUrl, { data }] = useLazyGetIntegrationOauthUrlQuery();
    const [handleOauthCallback] = useHandleIntegrationOauthCallbackMutation();

    const [parameters, setParameters] = useState<any>({});
    const workspace = useAppSelector(selectWorkspace);
    const router = useRouter();
    const [error, setError] = useState(false);

    const user = useAppSelector(selectAuth);
    const [showIntegrationConsent, setShowIntegrationConsent] = useState(false);
    const [errorMessage, setErrorMessage] = useState('');
    const [oauthResult, setOauthResult] = useState({ state: '', code: '' });

    useEffect(() => {
        if (action.name === 'creator_copy_mail') {
            setParameters({ ['Receiving Mail Address']: user.email });
        } else if (action.name === IntegrationType.GoogleSheet) {
            setShowIntegrationConsent(true);
        }
    }, [action]);

    useEffect(() => {
        if (oauthResult.code && oauthResult.state) {
            const body = { ...oauthResult, action_id: action.id, form_id: form.formId };
            const request = {
                body,
                integrationType: IntegrationType.GoogleSheet
            };
            handleOauthCallback(request).then((result: any) => {
                if (result?.data) {
                    setShowIntegrationConsent(false);
                }
            });
        }
    }, [oauthResult.state]);

    const handleClick = () => {
        setErrorMessage('');
        fetchOauthUrl({ integrationType: IntegrationType.GoogleSheet }).then((res) => {
            window.open(res.data, 'oauthWindow', 'height=600 width=600 left=600 top=300');
        });
    };

    if (showIntegrationConsent) {
        return (
            <div className={'flex flex-col gap-4 bg-white p-20'}>
                <h1>Connect Google Sheet</h1>
                <AppButton onClick={handleClick}>Connect</AppButton>
                {errorMessage && <h1 className={'text-red-500'}>{errorMessage}</h1>}
            </div>
        );
    }

    // listen for oauth event
    window.addEventListener('message', function (event) {
        if (event.origin === `${environments.HTTP_SCHEME}${environments.ADMIN_DOMAIN}`) {
            if (event.data?.error) {
                setErrorMessage('Access has been denied');
            } else if (event.data?.state && event.data?.code) {
                setOauthResult({ state: event.data?.state, code: event.data?.code });
            }
        }
    });

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
            router.push(router.asPath);
            toast('Added', { type: 'success' });
            closeModal();
        } else if (response?.error) {
            toast('Error', { type: 'error' });
        }
        setError(error);
    };

    return (
        <HeaderModalWrapper headerTitle="Add integration to form">
            <div className="flex flex-col md:min-w-[400px]">
                <div className="h4-new">
                    Adding {action?.title || 'Untitled'} to the form {form?.title || 'Untitled'}
                </div>
                {action?.parameters?.filter((param: any) => param.required).length > 0 && (
                    <>
                        <div className="text-black-800 w-full">Params required to add action:</div>
                        {action?.parameters?.map((parameter: any, index: number) =>
                            parameter?.required ? (
                                <div key={index} className="mt-3 flex w-full  flex-col items-start gap-2">
                                    <div className="text-sm font-bold">{parameter.name}</div>
                                    <AppTextField
                                        className="w-full"
                                        value={parameters[parameter.name]}
                                        onChange={(event: any) => {
                                            setParameters({ ...parameters, [parameter.name]: event.target.value });
                                        }}
                                    />
                                </div>
                            ) : (
                                <div key={index}></div>
                            )
                        )}
                        {error && <div className="text-sm text-red-500 ">Please fill in all required parameters.</div>}
                    </>
                )}

                <AppButton data-umami-event={`Add ${action?.title} Integration`} data-umami-event-email={user.email} className="mt-4" variant={ButtonVariant.Primary} size={ButtonSize.Medium} onClick={onAddIntegration}>
                    Add Integrations
                </AppButton>
            </div>
        </HeaderModalWrapper>
    );
}
