import React, { useEffect, useState } from 'react';

import { useTranslation } from 'next-i18next';

import Joyride from '@Components/Joyride';
import { JoyrideStepContent, JoyrideStepTitle } from '@Components/Joyride/JoyrideStepTitleAndContent';
import { Autocomplete, Box, TextField, createFilterOptions } from '@mui/material';
import MuiButton from '@mui/material/Button';
import { toast } from 'react-toastify';

import ImportErrorView from '@app/components/form-integrations/import-error-view';
import { TypeformIcon } from '@app/components/icons/brands/typeform';
import { Close } from '@app/components/icons/close';
import { GoogleFormIcon } from '@app/components/icons/google-form-icon';
import { useModal } from '@app/components/modal-views/context';
import Button from '@app/components/ui/button';
import FullScreenLoader from '@app/components/ui/fullscreen-loader';
import ActiveLink from '@app/components/ui/links/active-link';
import environments from '@app/configs/environments';
import { buttonConstant } from '@app/constants/locales/button';
import { importFormConstant } from '@app/constants/locales/import-form';
import { toastMessage } from '@app/constants/locales/toast-message';
import { Provider } from '@app/models/enums/provider';
import { useAppSelector } from '@app/store/hooks';
import { JOYRIDE_CLASS, JOYRIDE_ID } from '@app/store/tours/types';
import { useImportFormMutation, useLazyGetMinifiedFormsQuery, useLazyGetSingleFormFromProviderQuery } from '@app/store/workspaces/api';

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
    const { closeModal } = useModal();
    const { t } = useTranslation();
    const [provider, setProvider] = useState(props?.provider ?? null);

    const [integrations, setIntegrations] = useState<Array<IIntegrations>>([]);
    const [stepCount, setStepCount] = useState(0);
    const [selectedForm, setSelectedForm] = useState<IAutoCompleteFormValueProps | null>(null);
    const [responseDataOwner, setResponseDataOwner] = useState<IAutoCompleteFormFieldProps | null>(null);

    const workspace = useAppSelector((state) => state.workspace);

    const [minifiedFormsTrigger, minifiedFormsResult] = useLazyGetMinifiedFormsQuery();
    const minifiedFormList = !!minifiedFormsResult?.isFetching || !minifiedFormsResult?.data ? [] : minifiedFormsResult?.data ?? [];

    const [singleFormFromProviderTrigger, singleFormFromProviderResult] = useLazyGetSingleFormFromProviderQuery();
    const singleFormFieldList = !!singleFormFromProviderResult?.isFetching || !singleFormFromProviderResult?.data?.clientFormItems ? [] : singleFormFromProviderResult?.data?.clientFormItems ?? [];

    const [importForm, importFormResult] = useImportFormMutation();

    const requestAnIntegration = {
        href: 'https://forms.bettercollected.com/bettercollected/forms/request-integration',
        name: t(buttonConstant.requestAnIntegration)
    };

    const cleanup = () => {
        setProvider(null);
        setSelectedForm(null);
        setResponseDataOwner(null);
    };

    const handleImportForm = async () => {
        const form: any = { ...singleFormFromProviderResult?.data, provider };
        delete form['clientFormItems'];
        const response: any = await importForm({
            body: { form, response_data_owner: responseDataOwner?.questionId ?? '' },
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

    const handleNext = async (provider?: string) => {
        setProvider(provider);
        if (stepCount < 2) setStepCount(stepCount + 1);
    };

    const responseOwnerTag = {
        title: t(provider === Provider.google ? importFormConstant.responseOwnerTagTitleGoogle : importFormConstant.responseOwnerTagTitleTypeform),
        description: t(provider === Provider.google ? importFormConstant.responseOwnerTagDescriptionGoogle : importFormConstant.responseOwnerTagDescriptionTypeform),
        label: t(provider === Provider.google ? importFormConstant.responseOwnerTagLabelGoogle : importFormConstant.responseOwnerTagLabelTypeform)
    };

    useEffect(() => {
        if (provider) {
            (async () => await minifiedFormsTrigger({ provider }))().then(() => handleNext(provider));
        }
        if (props?.providers) {
            const allProviders: Array<IIntegrations> = [];
            Object.keys(props?.providers).forEach((p) => {
                if (p === 'google' && props?.providers[p])
                    allProviders.push({
                        provider: 'google',
                        icon: <GoogleFormIcon className="h-[70px] w-[70px] md:h-[100px] md:w-[100px]" />,
                        name: 'Google Forms',
                        onClick: () => handleNext('google')
                    });
                if (p === 'typeform' && props?.providers[p])
                    allProviders.push({
                        provider: 'typeform',
                        icon: <TypeformIcon className="h-[70px] w-[70px] md:h-[100px] md:w-[100px]" />,
                        name: 'Typeform',
                        onClick: () => handleNext('typeform')
                    });
            });
            setIntegrations(allProviders);
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [props]);

    useEffect(() => {
        if (stepCount === 0) {
            cleanup();
        }
        if (stepCount === 1 && provider) {
            (async () => await minifiedFormsTrigger({ provider }))();
        }
        if (stepCount === 2 && provider && selectedForm) {
            (async () => await singleFormFromProviderTrigger({ formId: selectedForm?.formId, provider }))();
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [stepCount, provider, selectedForm]);

    const stepZeroContent = (
        <>
            <h4 className="sh1 text-center">{t(importFormConstant.choice)}</h4>
            <div className={` flex justify-center w-full h-full gap-4 lg:gap-10 ${JOYRIDE_CLASS.WORKSPACE_ADMIN_FORM_IMPORT_PROVIDER_SELECTION}`}>
                {integrations.map((integration) => (
                    <MuiButton key={integration.provider} sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center' }} onClick={integration.onClick} className="sh1 h-[120px] w-full md:h-[200px] md:w-[200px] !text-brand-500 capitalize">
                        <div className="h-full w-full flex flex-col items-center justify-center gap-5">
                            {integration.icon}
                            <span className="body4 !not-italic !font-medium font-roboto tracking-wide !text-black-700">{integration.name}</span>
                        </div>
                    </MuiButton>
                ))}
            </div>
            <ActiveLink href={requestAnIntegration.href} className="body4 !not-italic !text-brand-500 hover:!text-brand-600">
                {requestAnIntegration.name}
            </ActiveLink>
        </>
    );

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
                            title: <JoyrideStepTitle text="Select your form" />,
                            content: (
                                <JoyrideStepContent>
                                    Select the form that you want to import. <br />
                                    <br /> If you do not see any forms in the list, then you may need to create some forms within the form provider account that you selected (Google Forms, Typeform).
                                </JoyrideStepContent>
                            ),
                            target: `.${JOYRIDE_CLASS.WORKSPACE_ADMIN_FORM_IMPORT_LIST_FORMS}`,
                            placementBeacon: 'top-end',
                            hideFooter: true
                        }
                    ]}
                />
            )}
            <h4 className="sh1 w-full text-start">{t(importFormConstant.title)}</h4>
            <div className="flex flex-col w-full h-full gap-10 items-end">
                <Autocomplete
                    loading={!!minifiedFormsResult?.isFetching}
                    disablePortal
                    id="form_list"
                    className={JOYRIDE_CLASS.WORKSPACE_ADMIN_FORM_IMPORT_LIST_FORMS}
                    fullWidth
                    onChange={(e, value) => setSelectedForm(value)}
                    value={selectedForm}
                    filterOptions={createFilterOptions({
                        matchFrom: 'start',
                        stringify: (option: IAutoCompleteFormValueProps) => option.label
                    })}
                    isOptionEqualToValue={(option: IAutoCompleteFormValueProps, value: IAutoCompleteFormValueProps) => option.formId === value.formId}
                    getOptionLabel={(option: IAutoCompleteFormValueProps) => option.label}
                    options={minifiedFormList}
                    sx={{ width: '100%' }}
                    renderOption={(props, option: IAutoCompleteFormValueProps) => {
                        return (
                            <Box component="li" {...props} key={option.formId}>
                                {option.label}
                            </Box>
                        );
                    }}
                    renderInput={(params) => <TextField {...params} label={provider === Provider.google ? t(importFormConstant.textLabel.googleForm) : t(importFormConstant.textLabel.typeform)} />}
                />
                <div>
                    <Button isLoading={!!minifiedFormsResult?.isLoading} onClick={() => handleNext(provider)} disabled={!selectedForm} size="medium">
                        {t(buttonConstant.next)}
                    </Button>
                </div>
            </div>
        </>
    );

    const stepTwoContent = (
        <>
            {environments.ENABLE_JOYRIDE_TOURS && (
                <Joyride
                    id={JOYRIDE_ID.WORKSPACE_ADMIN_FORM_IMPORT_DATA_OWNER}
                    continuous={false}
                    placement="top"
                    scrollOffset={0}
                    steps={[
                        {
                            title: <JoyrideStepTitle text="Select the data owner field for your form response" />,
                            content: (
                                <JoyrideStepContent>
                                    Select your own field to be set as the data owner identifier. <br />
                                    <br /> When responders respond to this form, data owner simply means the field you selected will be used to identify your responders. Typically, this will be an email, a phone number, or any other identifier unique to
                                    your responders.
                                </JoyrideStepContent>
                            ),
                            target: `.${JOYRIDE_CLASS.WORKSPACE_ADMIN_FORM_IMPORT_DATA_OWNER}`,
                            placementBeacon: 'top-end',
                            hideFooter: true
                        }
                    ]}
                />
            )}
            <h4 className="h4 w-full text-start">{responseOwnerTag.title}</h4>
            <div className="flex flex-col gap-5 w-full">
                <p className="body1">{responseOwnerTag.description}</p>
                <div className="flex flex-col w-full h-full gap-6 items-end">
                    <Autocomplete
                        loading={!!singleFormFromProviderResult?.isFetching}
                        disablePortal
                        id="field_list"
                        className={JOYRIDE_CLASS.WORKSPACE_ADMIN_FORM_IMPORT_DATA_OWNER}
                        fullWidth
                        onChange={(e, value) => setResponseDataOwner(value)}
                        value={responseDataOwner}
                        filterOptions={createFilterOptions({
                            matchFrom: 'start',
                            stringify: (option: IAutoCompleteFormFieldProps) => option.label
                        })}
                        isOptionEqualToValue={(option: IAutoCompleteFormFieldProps, value: IAutoCompleteFormFieldProps) => option.questionId === value.questionId}
                        getOptionLabel={(option: IAutoCompleteFormFieldProps) => option.label}
                        options={singleFormFieldList}
                        sx={{ width: '100%' }}
                        renderOption={(props, option: IAutoCompleteFormFieldProps) => {
                            return (
                                <Box component="li" {...props} key={option.questionId}>
                                    {option.label}
                                </Box>
                            );
                        }}
                        renderInput={(params) => <TextField {...params} label={responseOwnerTag.label} />}
                    />
                    <Button className="!font-medium" isLoading={!!importFormResult?.isLoading || !!singleFormFromProviderResult?.isLoading} onClick={handleImportForm} disabled={!selectedForm || !!singleFormFromProviderResult?.isLoading} size="medium">
                        {t(buttonConstant.importNow)}
                    </Button>
                </div>
            </div>
        </>
    );

    if (minifiedFormsResult?.isLoading) return <FullScreenLoader />;

    if (minifiedFormsResult?.isError) return <ImportErrorView provider={provider} />;

    return (
        <div className="relative z-50 mx-auto max-w-full min-w-full md:max-w-[600px] md:min-w-[600px] lg:max-w-[600px] lg:min-w-[600px]" {...props}>
            <div className="rounded-[4px] relative m-auto max-w-[500px] md:min-w-[500px] items-start justify-between bg-white">
                <div className="relative flex flex-col items-center gap-7 justify-between p-4 md:p-10">
                    {stepCount === 0 && stepZeroContent}
                    {stepCount === 1 && stepOneContent}
                    {stepCount === 2 && stepTwoContent}
                </div>
                <div className="cursor-pointer absolute top-3 right-3 text-gray-600 hover:text-black" onClick={() => closeModal()}>
                    <Close className="h-auto w-3 text-gray-600 dark:text-white" />
                </div>
            </div>
        </div>
    );
}
