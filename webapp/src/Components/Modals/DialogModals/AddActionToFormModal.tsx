import { useEffect, useState } from 'react';

import { useRouter } from 'next/router';

import AppTextField from '@Components/Common/Input/AppTextField';
import AppButton from '@Components/Common/Input/Button/AppButton';
import { ButtonSize, ButtonVariant } from '@Components/Common/Input/Button/AppButtonProps';
import HeaderModalWrapper from '@Components/Modals/ModalWrappers/HeaderModalWrapper';
import { toast } from 'react-toastify';

import { useHandleIntegrationOauthCallbackMutation, useLazyGetIntegrationOauthUrlQuery } from '@app/store/integrationApi';
import { useModal } from '@app/Components/modal-views/context';
import { useAddActionToFormMutation } from '@app/store/api-actions-api';
import { selectAuth } from '@app/store/auth/slice';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { IntegrationType } from '@app/models/enums/IntegrationTypeEnum';
import environments from '@app/configs/environments';
import Image from 'next/image';

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
            <HeaderModalWrapper headerTitle="Add Google Sheets to form">
                <div className="relative flex flex-col rounded-xl p-8 md:min-w-[400px]">
                    <div className="mb-6 flex justify-center">
                        <Image src={action?.url || '/integration/default.svg'} alt="Google Sheets Icon" width={80} height={80} />
                    </div>
                    <div className="mb-4 text-center text-2xl font-bold text-gray-800">
                        <span className="text-blue-600">{action?.title || 'Untitled'}</span> to the form <span className="text-blue-600">{form?.title || 'Untitled'}</span>
                    </div>
                    <p className="text-center text-sm text-gray-600 ">Send your BetterCollected form responses to your Google Sheets</p>
                    <AppButton className="mt-4" onClick={handleClick}>
                        Connect to Google{' '}
                    </AppButton>
                    {errorMessage && <h1 className={'mt-4 text-red-500'}>{errorMessage}</h1>}
                </div>
            </HeaderModalWrapper>
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
            {/* This is the front popup */}
            <div className="relative flex flex-col rounded-xl  p-8  md:min-w-[400px]">
                {/* Top Banner/Icon Section with Illustrations */}
                <div className="mb-6 flex justify-center">
                    <Image src={action?.url || '/integration/default.svg'} alt="Integration Icon" width={80} height={80} />
                </div>

                {/* Title with Enhanced Typography */}
                <div className="mb-4 text-center text-2xl font-bold text-gray-800">
                    Adding <span className="text-blue-600">{action?.title || 'Untitled'}</span> to the form <span className="text-blue-600">{form?.title || 'Untitled'}</span>
                </div>

                {/* Floating Label Input Fields */}
                {action?.parameters?.filter((param: any) => param.required).length > 0 && (
                    <>
                        <div className="mb-2 text-lg font-semibold text-gray-700">Required Parameters</div>
                        <div className="space-y-4">
                            {action?.parameters?.map((parameter: any, index: number) =>
                                parameter?.required ? (
                                    <div key={index} className="relative">
                                        <AppTextField
                                            className="w-full"
                                            placeholder={parameter.name}
                                            value={parameters[parameter.name]}
                                            onChange={(event) => {
                                                setParameters({ ...parameters, [parameter.name]: event.target.value });
                                            }}
                                        />
                                    </div>
                                ) : (
                                    <div key={index}></div>
                                )
                            )}
                        </div>
                        {error && <div className="mt-2 text-sm text-red-500">Please fill in all required parameters.</div>}
                    </>
                )}

                {/* Add Integration Button */}
                <AppButton data-umami-event={`Add ${action?.title} Integration`} data-umami-event-email={user.email} variant={ButtonVariant.Primary} size={ButtonSize.Medium} onClick={onAddIntegration} className="mt-4">
                    Add Integration
                </AppButton>
            </div>
        </HeaderModalWrapper>
    );
}
