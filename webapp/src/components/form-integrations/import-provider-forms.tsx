import React, {useEffect, useState} from 'react';

import {useTranslation} from 'next-i18next';
import {useRouter} from 'next/router';

import Divider from '@Components/Common/DataDisplay/Divider';
import AppButton from '@Components/Common/Input/Button/AppButton';
import {ButtonSize} from '@Components/Common/Input/Button/AppButtonProps';
import Joyride from '@Components/Joyride';
import {JoyrideStepContent, JoyrideStepTitle} from '@Components/Joyride/JoyrideStepTitleAndContent';
import {Autocomplete, Box, TextField, createFilterOptions} from '@mui/material';
import MuiButton from '@mui/material/Button';
import {toast} from 'react-toastify';

import ImportErrorView from '@app/components/form-integrations/import-error-view';
import {TypeformIcon} from '@app/components/icons/brands/typeform';
import {Close} from '@app/components/icons/close';
import {GoogleFormIcon} from '@app/components/icons/google-form-icon';
import {useModal} from '@app/components/modal-views/context';
import FullScreenLoader from '@app/components/ui/fullscreen-loader';
import ActiveLink from '@app/components/ui/links/active-link';
import environments from '@app/configs/environments';
import {buttonConstant} from '@app/constants/locales/button';
import {importFormConstant} from '@app/constants/locales/import-form';
import {toastMessage} from '@app/constants/locales/toast-message';
import {Provider} from '@app/models/enums/provider';
import {setBuilderState} from '@app/store/form-builder/actions';
import {initBuilderState} from '@app/store/form-builder/builderSlice';
import {useAppDispatch, useAppSelector} from '@app/store/hooks';
import {JOYRIDE_CLASS, JOYRIDE_ID} from '@app/store/tours/types';
import {
    useCreateFormMutation,
    useImportFormMutation,
    useLazyGetMinifiedFormsQuery,
    useLazyGetSingleFormFromProviderQuery
} from '@app/store/workspaces/api';
import AppTextField from "@Components/Common/Input/AppTextField";
import {setForm} from "@app/store/forms/slice";

interface IIntegrations {
    provider: string;
    icon: React.ReactElement;
    name: string;
    onClick: any;
}

interface IAutoCompleteFormValueProps {
    label: string;
    formId: string;
}

interface IAutoCompleteFormFieldProps {
    label: string;
    questionId: string;
}

export default function ImportProviderForms(props: any) {
    const {closeModal} = useModal();
    const {t} = useTranslation();
    const [provider, setProvider] = useState(props?.provider ?? 'google');

    const [responseDataOwner, setResponseDataOwner] = useState<IAutoCompleteFormFieldProps | null>(null);

    const workspace = useAppSelector((state) => state.workspace);


    const [singleFormFromProviderTrigger, singleFormFromProviderResult] = useLazyGetSingleFormFromProviderQuery();

    const [importForm, importFormResult] = useImportFormMutation();

    const [formId, setFormId] = useState("")
    const [error, setError] = useState(false)

    const [importFormLink, setImportFormLink] = useState("")

    const router = useRouter();
    const [postCreateForm, {isLoading: posting}] = useCreateFormMutation();
    const dispatch = useAppDispatch();

    const [showErrorView, setShowError] = useState(false)

    useEffect(() => {
        const pattern = /https:\/\/docs\.google\.com\/forms\/d\/([^/]+)\/edit/;

        const match = importFormLink.match(pattern);

        if (match) {
            const formId = match[1];
            setFormId(formId)
            setError(false)
        } else {
            setFormId("");
            setError(true)
        }
    }, [importFormLink])

    const cleanup = () => {
        setProvider(null);
        setResponseDataOwner(null);
    };

    const handleImportForm = async () => {

        const singleForm = await singleFormFromProviderTrigger({provider: "google", formId: formId})
        const form: any = {...singleForm?.data, provider};
        delete form['clientFormItems'];
        if (singleForm.error) {
            setShowError(true)
            return
        }
        const response: any = await importForm({
            body: {form, response_data_owner: responseDataOwner?.questionId ?? ''},
            provider,
            workspaceId: workspace.id
        });
        if (response.data) {
            toast.success(t(toastMessage.formImportedSuccessfully).toString());
            cleanup();
            closeModal();
        } else {
            toast.error(response.error?.data || t(toastMessage.couldNotImportedForm));
        }
    };

    const createNewForm = async () => {
        const formData = new FormData();
        const postReq: any = {};
        postReq.title = initBuilderState.title;
        postReq.description = initBuilderState.description;
        postReq.fields = Object.values(initBuilderState.fields);
        postReq.buttonText = initBuilderState.buttonText;
        postReq.consent = [];
        postReq.settings = {};
        formData.append('form_body', JSON.stringify(postReq));
        const apiObj: any = {workspaceId: workspace.id, body: formData};
        const response: any = await postCreateForm(apiObj);

        if (response?.data) {
            router.push(`/${workspace?.workspaceName}/dashboard/forms/${response?.data?.formId}/edit`);
            dispatch(setBuilderState({isFormDirty: false}));
        }
    };

    const stepOneContent = (
        <>
            {environments.ENABLE_JOYRIDE_TOURS && (
                <Joyride
                    id={JOYRIDE_ID.WORKSPACE_ADMIN_FORM_IMPORT_LIST_FORMS}
                    continuous={false}
                    placement="top"
                    scrollOffset={0}
                    steps={[
                        {
                            title: <JoyrideStepTitle text="Select your form"/>,
                            content: (
                                <JoyrideStepContent>
                                    Select the form that you want to import. <br/>
                                    <br/> If you do not see any forms in the list, then you may need to create some
                                    forms within the form provider account that you selected (Google Forms, Typeform).
                                </JoyrideStepContent>
                            ),
                            target: `.${JOYRIDE_CLASS.WORKSPACE_ADMIN_FORM_IMPORT_LIST_FORMS}`,
                            placementBeacon: 'top-end',
                            hideFooter: true
                        }
                    ]}
                />
            )}
            <h4 className="h6 !text-black-800 !font-medium text-center">{provider === Provider.google ? 'Copy Google Form Edit Link' : 'Select TypeForm'}</h4>
            <div className={'text-sm font-normal text-black-700 '}>
                Paste the edit page link of your google form. If there
                are no existing forms, you can always
                <span onClick={createNewForm}
                     className="pl-1 body4 !not-italic !text-brand-500 hover:!text-brand-600 cursor-pointer">
                    Create bettercollected Form.
                </span>
            </div>
            <div className="flex flex-col w-full h-full gap-4 mt-4">
                <AppTextField value={importFormLink} onChange={(event) => {
                    setImportFormLink(event.target.value)
                }}/>
                <AppButton
                    className={'!w-full'}
                    isLoading={!!importFormResult?.isLoading || !!singleFormFromProviderResult?.isLoading}
                    onClick={handleImportForm}
                    disabled={error}
                    size={ButtonSize.Medium}
                >
                    {t(buttonConstant.importNow)}
                </AppButton>
            </div>
        </>
    );

    if (showErrorView) return <ImportErrorView provider={provider}/>;

    return (
        <div
            className="relative z-50 mx-auto max-w-full min-w-full md:max-w-[600px] md:min-w-[600px] lg:max-w-[600px] lg:min-w-[600px]" {...props}>
            <div
                className="rounded-2xl relative m-auto max-w-[600px] md:min-w-[500px] items-start justify-between bg-white">
                <div className={'flex justify-between p-4'}>
                    <h1 className={'text-sm font-normal text-black-700'}>Import Form</h1>
                    <Close onClick={() => closeModal()} strokeWidth={2}/>
                </div>
                <Divider/>
                <div className="relative flex flex-col items-start gap-2 justify-between p-4 md:p-10 md:pt-6">
                    {stepOneContent}
                </div>
            </div>
        </div>
    );
}
