import { useEffect, useState } from 'react';

import { Autocomplete, Box, TextField, createFilterOptions } from '@mui/material';
import MuiButton from '@mui/material/Button';
import { toast } from 'react-toastify';

import ImportErrorView from '@app/components/form-integrations/import-error-view';
import { TypeformIcon } from '@app/components/icons/brands/typeform';
import { ChevronForward } from '@app/components/icons/chevron-forward';
import { Close } from '@app/components/icons/close';
import { GoogleFormIcon } from '@app/components/icons/google-form-icon';
import { useModal } from '@app/components/modal-views/context';
import Button from '@app/components/ui/button';
import FullScreenLoader from '@app/components/ui/fullscreen-loader';
import ActiveLink from '@app/components/ui/links/active-link';
import { useAppSelector } from '@app/store/hooks';
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
        name: 'Request an integration'
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
            toast.success('Form imported successfully.');
            cleanup();
            closeModal();
        } else {
            toast.error('Could not import the form.');
        }
    };

    const handleBack = () => {
        setStepCount(stepCount - 1);
        setResponseDataOwner(null);
    };

    const handleNext = async (provider?: string) => {
        setProvider(provider);
        if (stepCount < 2) setStepCount(stepCount + 1);
    };

    useEffect(() => {
        if (provider) {
            (async () => await minifiedFormsTrigger({ provider }))().then(() => handleNext(provider));
        }
        if (!!props?.providers) {
            const allProviders: Array<IIntegrations> = [];
            Object.keys(props?.providers).forEach((p) => {
                if (p === 'google')
                    allProviders.push({
                        provider: 'google',
                        icon: <GoogleFormIcon className="h-[70px] w-[70px] md:h-[100px] md:w-[100px]" />,
                        name: 'Google Forms',
                        onClick: () => handleNext('google')
                    });
                if (p === 'typeform')
                    allProviders.push({
                        provider: 'typeform',
                        icon: <TypeformIcon className="h-[70px] w-[70px] md:h-[100px] md:w-[100px]" />,
                        name: 'Typeform',
                        onClick: () => handleNext('typeform')
                    });
            });
            setIntegrations(allProviders);
        }
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
    }, [stepCount, provider, selectedForm]);

    const stepZeroContent = (
        <>
            <h4 className="sh1 text-center">Which form do you want to import?</h4>
            <div className="grid grid-cols-2 w-full h-full gap-4 lg:gap-10">
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

    const backBreadcrumb = (
        <p onClick={handleBack} className="body4 w-full cursor-pointer text-start flex items-center gap-2 hover:text-brand-500">
            <ChevronForward className="font-thin rotate-180" />
            Back
        </p>
    );

    const stepOneContent = (
        <>
            <h4 className="sh1 w-full text-start">Import form</h4>
            <div className="flex flex-col w-full h-full gap-10 items-end">
                <Autocomplete
                    loading={!!minifiedFormsResult?.isFetching}
                    disablePortal
                    id="form_list"
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
                    renderInput={(params) => <TextField {...params} label="Choose your form that you want to import" />}
                />
                <div>
                    <Button onClick={() => handleNext(provider)} disabled={!selectedForm} size="medium">
                        Next
                    </Button>
                </div>
            </div>
        </>
    );

    const stepTwoContent = (
        <>
            {backBreadcrumb}
            <h4 className="sh1 w-full text-start">Response data owner</h4>
            <p className="body1">Select another data response owner if the collect email setting is disabled in your form</p>
            <div className="flex flex-col w-full h-full gap-10 items-end">
                <Autocomplete
                    loading={!!singleFormFromProviderResult?.isFetching}
                    disablePortal
                    id="field_list"
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
                    renderInput={(params) => <TextField {...params} label="Choose a data owner field for this form" />}
                />
                <div>
                    <Button isLoading={!!importFormResult?.isLoading} onClick={handleImportForm} disabled={!selectedForm} size="medium">
                        Import
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
                <div className="relative flex flex-col items-center gap-10 justify-between p-4 md:p-10">
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
