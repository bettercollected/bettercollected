import React from 'react';

import { useTranslation } from 'next-i18next';
import { useRouter } from 'next/router';

import Divider from '@Components/Common/DataDisplay/Divider';
import Tooltip from '@Components/Common/DataDisplay/Tooltip';
import { DotIcon } from '@Components/Common/Icons/Common/DotIcon';
import SettingsIcon from '@Components/Common/Icons/Common/Settings';
import FormProviderIcon from '@Components/Common/Icons/Form/FormProviderIcon';
import Preview from '@Components/Common/Icons/Form/Preview';
import AppButton from '@Components/Common/Input/Button/AppButton';
import { ButtonVariant } from '@Components/Common/Input/Button/AppButtonProps';
import Joyride from '@Components/Joyride';
import { JoyrideStepContent, JoyrideStepTitle } from '@Components/Joyride/JoyrideStepTitleAndContent';
import { ChevronLeft } from '@mui/icons-material';

import FormRenderer from '@app/components/form/renderer/form-renderer';
import { useModal } from '@app/components/modal-views/context';
import { useFullScreenModal } from '@app/components/modal-views/full-screen-modal-context';
import FullScreenLoader from '@app/components/ui/fullscreen-loader';
import ParamTab, { TabPanel } from '@app/components/ui/param-tab';
import environments from '@app/configs/environments';
import { buttonConstant } from '@app/constants/locales/button';
import { localesCommon } from '@app/constants/locales/common';
import { toolTipConstant } from '@app/constants/locales/tooltip';
import Layout from '@app/layouts/_layout';
import { JOYRIDE_CLASS, JOYRIDE_ID } from '@app/store/tours/types';
import { utcToLocalDate } from '@app/utils/dateUtils';

interface SubmissionProps {
    hasCustomDomain: boolean;
    data: any;
    handleRequestForDeletion: any;
}

export default function Submission({ hasCustomDomain, data, handleRequestForDeletion }: SubmissionProps) {
    const { isLoading, isError } = data;
    const form: any = data ?? {};
    const router = useRouter();

    const { t } = useTranslation();
    const { openModal, closeModal } = useModal();

    const fullScreenModal = useFullScreenModal();

    const paramTabs = [
        {
            icon: <Preview className="h-5 w-5" />,
            title: 'Form',
            path: 'Form'
        },
        {
            icon: <SettingsIcon className="h-5 w-5" />,
            title: t(localesCommon.settings),
            path: 'Settings'
        }
    ];

    const goToSubmissions = () => {
        let pathName;
        if (hasCustomDomain) {
            pathName = '/';
        } else {
            pathName = `/${router.query.workspace_name}`;
        }

        router
            .push(
                {
                    pathname: pathName,
                    query: { view: 'mySubmissions' }
                },
                undefined,
                { scroll: true, shallow: true }
            )
            .then((r) => r)
            .catch((e) => e);
    };

    const deletionStatus = !!form?.response?.deletionStatus;

    const handleRequestForDeletionModal = () => {
        openModal('REQUEST_FOR_DELETION_VIEW', { handleRequestForDeletion: handleRequestForDeletion });
    };

    return (
        <Layout className="bg-white !px-0" showAuthAccount={false} isCustomDomain={hasCustomDomain} isClientDomain={!hasCustomDomain} showNavbar={true}>
            {isLoading || isError || !data ? (
                <FullScreenLoader />
            ) : (
                <div className="mt-5 flex flex-col pb-6">
                    {environments.ENABLE_JOYRIDE_TOURS && (
                        <Joyride
                            id={JOYRIDE_ID.RESPONDERS_PORTAL}
                            scrollOffset={68}
                            placement="bottom-end"
                            floaterProps={{ autoOpen: true }}
                            steps={[
                                {
                                    title: <JoyrideStepTitle text="Deletion Request" />,
                                    content: <JoyrideStepContent>You can request for submission deletion.</JoyrideStepContent>,
                                    target: `.${JOYRIDE_CLASS.RESPONDERS_SUBMISSION_DELETE}`,
                                    placementBeacon: 'bottom-end',
                                    disableBeacon: false
                                }
                            ]}
                        />
                    )}

                    <div className="w-full px-5">
                        <div className="flex items-center justify-start gap-2 w-fit " onClick={goToSubmissions}>
                            <ChevronLeft className="cursor-pointer" strokeWidth={2} width={24} height={24} />
                            <span className="text-black-800 text-sm cursor-pointer">Form Page</span>
                            <ChevronLeft className="text-black-600 rotate-180" strokeWidth={1} width={24} height={24} />
                            <span className="text-black-600  text-sm"> My response</span>
                        </div>
                    </div>
                    <div className="w-full flex flex-col mt-12 gap-2 px-5 md:px-10 lg:px-28">
                        <span className="!text-pink h2-new">{form?.form?.title || 'Untitled Form'}</span>
                        <div className="text-black-600 text-sm flex flex-wrap gap-2 items-center">
                            <FormProviderIcon provider={form?.form?.settings?.provider} />
                            <DotIcon />
                            <div className="min-w-fit">Submitted: {utcToLocalDate(form?.response?.createdAt)}</div>
                        </div>
                        <Divider className="mt-6" />
                    </div>
                    <ParamTab showInfo={true} className="px-5 lg:px-28 md:px-10 w-full" tabMenu={paramTabs}>
                        <div className="w-full mt-12">
                            <TabPanel key="Form">
                                <FormRenderer form={form.form} response={form.response} isDisabled />
                            </TabPanel>
                        </div>
                        <TabPanel key="Settings">
                            <div className="flex flex-col px-5 md:px-10 lg:px-28 gap-[72px]">
                                <div className="flex flex-col gap-2">
                                    <span className="h3-new">Settings</span>
                                    <span className="p2-new text-black-700"> Review your data usage permissions</span>
                                </div>
                                {form?.settings?.provider !== 'self' && (
                                    <div className="flex flex-col gap-4 max-w-[800px]">
                                        <Divider />
                                        <div className="h4-new">You can request for deletion of your data in this form.</div>
                                        <Divider />
                                    </div>
                                )}
                                {form?.form?.settings?.provider === 'self' && (
                                    <div className="flex flex-col gap-4 max-w-[800px]">
                                        <span className="h3-new">Form Purpose and Data Usage</span>
                                        <div className="py-4 border-y-[1px] border-black-300 flex flex-col md:flex-row w-full items-start md:items-center space-between">
                                            <span className="p2-new text-black-700"> View the permissions you&apos;ve granted for data usage, third-party integrations, data retention dates, and see who can access your data</span>
                                            <AppButton
                                                onClick={() => {
                                                    fullScreenModal.openModal('CONSENT_FULL_MODAL_VIEW', {
                                                        isDisabled: true,
                                                        form: form.response
                                                    });
                                                }}
                                                variant={ButtonVariant.Ghost}
                                            >
                                                See Details
                                            </AppButton>
                                        </div>
                                    </div>
                                )}
                                {!form?.response?.deletionStatus ? (
                                    <div>
                                        <Tooltip title={deletionStatus ? t(toolTipConstant.alreadyRequestedForDeletion) : t(toolTipConstant.requestForDeletion)}>
                                            <AppButton className={`w-fit ${JOYRIDE_CLASS.RESPONDERS_SUBMISSION_DELETE}`} variant={ButtonVariant.Danger} onClick={handleRequestForDeletionModal}>
                                                {t(buttonConstant.requestForDeletion)}
                                            </AppButton>
                                        </Tooltip>
                                    </div>
                                ) : (
                                    <div className="flex flex-col gap-2">
                                        <span className="h4-new !text-red-500 ">You have requested for deletion of your response.</span>
                                        <span>Status: Pending</span>
                                    </div>
                                )}
                            </div>
                        </TabPanel>
                    </ParamTab>
                </div>
            )}
        </Layout>
    );
}
