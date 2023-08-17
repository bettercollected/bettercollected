import React from 'react';

import { useTranslation } from 'next-i18next';
import { useRouter } from 'next/router';

import Tooltip from '@Components/Common/DataDisplay/Tooltip';
import DeleteIcon from '@Components/Common/Icons/Delete';
import Button from '@Components/Common/Input/Button';
import Joyride from '@Components/Joyride';
import { JoyrideStepContent, JoyrideStepTitle } from '@Components/Joyride/JoyrideStepTitleAndContent';
import { ChevronLeft } from '@mui/icons-material';
import { toast } from 'react-toastify';

import FormRenderer from '@app/components/form/renderer/form-renderer';
import { useModal } from '@app/components/modal-views/context';
import FullScreenLoader from '@app/components/ui/fullscreen-loader';
import environments from '@app/configs/environments';
import { breadcrumbsItems } from '@app/constants/locales/breadcrumbs-items';
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
import { parseDateStrToDate, toMonthDateYearStr, utcToLocalDate } from '@app/utils/dateUtils';
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

    const [requestWorkspaceSubmissionDeletion] = useRequestWorkspaceSubmissionDeletionMutation();

    const { isLoading, isError, data } = useGetWorkspaceSubmissionQuery({
        workspace_id: workspace?.id ?? '',
        submission_id: submissionId
    });

    const form: any = data ?? [];

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
    const submittedAt = `${toMonthDateYearStr(parseDateStrToDate(utcToLocalDate(form?.response?.createdAt)))}`;

    return (
        <Layout showAuthAccount={false} isCustomDomain={hasCustomDomain} isClientDomain={!hasCustomDomain} showNavbar={true}>
            {isLoading || isError || !data ? (
                <FullScreenLoader />
            ) : (
                <div className="container mx-auto mt-5 flex flex-col  items-center px-6  pb-6">
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

                    <div className="w-full mb-8 absolute left-0 right-0 lg:px-20 px-5">
                        <div className="flex items-center justify-start gap-2 w-fit cursor-pointer" onClick={goToSubmissions}>
                            <ChevronLeft width={24} height={24} />
                            <span className="sh1 ">{t(breadcrumbsItems.mySubmissions)}</span>
                        </div>
                    </div>
                    <div className="flex-col-reverse lg:flex-row flex gap-5 lg:!gap-16 w-full pt-20">
                        <div className="bg-white rounded-xl w-full">
                            <FormRenderer form={form.form} response={form.response} />
                        </div>
                        <div className="flex flex-row-reverse justify-between lg:justify-start gap-10  lg:flex-col basis-1/4 ">
                            <div>
                                <Tooltip title={deletionStatus ? t(toolTipConstant.alreadyRequestedForDeletion) : t(toolTipConstant.requestForDeletion)}>
                                    <Button
                                        color="error"
                                        className={` ${JOYRIDE_CLASS.RESPONDERS_SUBMISSION_DELETE} w-auto min-w-[196px] z-10 capitalize !h-10 mt-0 body-6 !border-yellow-600  text-red rounded ${deletionStatus ? '!text-yellow-600' : ''} `}
                                        variant="outlined"
                                        onClick={handleRequestForDeletionModal}
                                        disabled={!!form?.response?.deletionStatus}
                                    >
                                        <span className="flex gap-2  items-center">
                                            <DeleteIcon className={!deletionStatus ? 'text-red-500' : ' text-yellow-700'} width={16} height={16} />
                                            {form?.response?.deletionStatus ? t(buttonConstant.requestedForDeletion) : t(buttonConstant.requestForDeletion)}
                                        </span>
                                    </Button>
                                </Tooltip>
                            </div>
                            <div>
                                <div className="body4 pb-2 text-black-700">{t(localesCommon.lastSubmittedAt)}</div>
                                <div className="text-black-900 body3">{submittedAt}</div>
                            </div>
                        </div>
                    </div>
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
