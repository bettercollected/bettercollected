import React from 'react';

import { useTranslation } from 'next-i18next';
import { useRouter } from 'next/router';

import Divider from '@Components/Common/DataDisplay/Divider';
import Tooltip from '@Components/Common/DataDisplay/Tooltip';
import { DotIcon } from '@Components/Common/Icons/DotIcon';
import FormProviderIcon from '@Components/Common/Icons/FormProviderIcon';
import Preview from '@Components/Common/Icons/Preview';
import SettingsIcon from '@Components/Common/Icons/Settings';
import AppButton from '@Components/Common/Input/Button/AppButton';
import { ButtonVariant } from '@Components/Common/Input/Button/AppButtonProps';
import Joyride from '@Components/Joyride';
import { JoyrideStepContent, JoyrideStepTitle } from '@Components/Joyride/JoyrideStepTitleAndContent';
import { ChevronLeft } from '@mui/icons-material';
import { toast } from 'react-toastify';

import FormRenderer from '@app/components/form/renderer/form-renderer';
import { useModal } from '@app/components/modal-views/context';
import { useFullScreenModal } from '@app/components/modal-views/full-screen-modal-context';
import FullScreenLoader from '@app/components/ui/fullscreen-loader';
import ParamTab, { TabPanel } from '@app/components/ui/param-tab';
import environments from '@app/configs/environments';
import { buttonConstant } from '@app/constants/locales/button';
import { localesCommon } from '@app/constants/locales/common';
import { toastMessage } from '@app/constants/locales/toast-message';
import { toolTipConstant } from '@app/constants/locales/tooltip';
import { ToastId } from '@app/constants/toastId';
import Layout from '@app/layouts/_layout';
import { useBreakpoint } from '@app/lib/hooks/use-breakpoint';
import { getGlobalServerSidePropsByDomain } from '@app/lib/serverSideProps';
import { StandardFormDto } from '@app/models/dtos/form';
import { IServerSideProps } from '@app/models/dtos/serverSideProps';
import { JOYRIDE_CLASS, JOYRIDE_ID } from '@app/store/tours/types';
import { useGetWorkspaceSubmissionQuery, useRequestWorkspaceSubmissionDeletionMutation } from '@app/store/workspaces/api';
import { utcToLocalDate } from '@app/utils/dateUtils';
import { checkHasCustomDomain, getServerSideAuthHeaderConfig } from '@app/utils/serverSidePropsUtils';

interface ISubmission extends IServerSideProps {
    form: StandardFormDto;
}

export default function Submission(props: any) {
    const { workspace, submissionId, hasCustomDomain }: ISubmission = props;
    const { t } = useTranslation();

    const router = useRouter();
    const breakpoint = useBreakpoint();
    const { openModal, closeModal } = useModal();
    const fullScreenModal = useFullScreenModal();

    const [requestWorkspaceSubmissionDeletion] = useRequestWorkspaceSubmissionDeletionMutation();

    const { isLoading, isError, data } = useGetWorkspaceSubmissionQuery({
        workspace_id: workspace?.id ?? '',
        submission_id: submissionId
    });

    const form: any = data ?? {};

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
    const handleRequestForDeletion = async () => {
        if (workspace && workspace.id && submissionId) {
            try {
                const query = {
                    workspace_id: workspace.id,
                    submission_id: submissionId
                };
                await requestWorkspaceSubmissionDeletion(query);
                toast(t(toastMessage.workspaceSuccess).toString(), { toastId: ToastId.SUCCESS_TOAST, type: 'success' });
                closeModal();
            } catch (e) {
                toast(t(toastMessage.somethingWentWrong).toString(), { toastId: ToastId.ERROR_TOAST, type: 'error' });
            }
        }
    };

    const handleRequestForDeletionModal = () => {
        openModal('REQUEST_FOR_DELETION_VIEW', { handleRequestForDeletion });
    };

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
    const submittedAt = `${utcToLocalDate(form?.response?.createdAt)}`;

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
                        <span className="!text-pink h2-new">{form?.title || 'Untitled Form'}</span>
                        <div className="text-black-600 text-sm flex flex-wrap gap-2 items-center">
                            <FormProviderIcon provider={form?.settings?.provider} />
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
                                {!form?.response?.deletionStatus ? (
                                    <div>
                                        <Tooltip title={deletionStatus ? t(toolTipConstant.alreadyRequestedForDeletion) : t(toolTipConstant.requestForDeletion)}>
                                            <AppButton className={` ${JOYRIDE_CLASS.RESPONDERS_SUBMISSION_DELETE}`} variant={ButtonVariant.Danger} onClick={handleRequestForDeletionModal}>
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

export async function getServerSideProps(_context: any) {
    const globalProps = (await getGlobalServerSidePropsByDomain(_context)).props;
    let form: StandardFormDto | null = null;
    const submissionId = _context.query.id;
    const hasCustomDomain = checkHasCustomDomain(_context);
    if (!hasCustomDomain) {
        return {
            redirect: {
                permanent: false,
                destination: '/'
            }
        };
    }

    if (!globalProps.workspace?.id) {
        return {
            notFound: true
        };
    }

    const config = getServerSideAuthHeaderConfig(_context);

    try {
        if (globalProps.hasCustomDomain && globalProps.workspaceId) {
            const formResponse = await fetch(`${environments.INTERNAL_DOCKER_API_ENDPOINT_HOST}/workspaces/${globalProps.workspaceId}/submissions/${submissionId}`, config).catch((e) => e);
            form = (await formResponse?.json().catch((e: any) => e)) ?? null;
        }
    } catch (err) {
        form = null;
    }

    return {
        props: {
            ...globalProps,
            form,
            submissionId
        }
    };
}
