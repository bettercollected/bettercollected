import React from 'react';

import { useTranslation } from 'next-i18next';
import { useRouter } from 'next/router';

import Tooltip from '@Components/Common/DataDisplay/Tooltip';
import { toast } from 'react-toastify';

import FormRenderer from '@app/components/form/renderer/form-renderer';
import { HomeIcon } from '@app/components/icons/home';
import { LongArrowLeft } from '@app/components/icons/long-arrow-left';
import { TrashIcon } from '@app/components/icons/trash';
import { useModal } from '@app/components/modal-views/context';
import Button from '@app/components/ui/button';
import FullScreenLoader from '@app/components/ui/fullscreen-loader';
import environments from '@app/configs/environments';
import { breadcrumbsItems } from '@app/constants/locales/breadcrumbs-items';
import { localesCommon } from '@app/constants/locales/common';
import { formConstant } from '@app/constants/locales/form';
import { toastMessage } from '@app/constants/locales/toast-message';
import { toolTipConstant } from '@app/constants/locales/tooltip';
import { ToastId } from '@app/constants/toastId';
import { useBreakpoint } from '@app/lib/hooks/use-breakpoint';
import { getGlobalServerSidePropsByDomain } from '@app/lib/serverSideProps';
import { StandardFormDto } from '@app/models/dtos/form';
import { IServerSideProps } from '@app/models/dtos/serverSideProps';
import { useGetWorkspaceSubmissionQuery, useRequestWorkspaceSubmissionDeletionMutation } from '@app/store/workspaces/api';
import { checkHasCustomDomain, getServerSideAuthHeaderConfig } from '@app/utils/serverSidePropsUtils';
import { toEndDottedStr } from '@app/utils/stringUtils';

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

    if (isLoading || isError || !data) return <FullScreenLoader />;

    const handleRequestForDeletion = async () => {
        if (workspace && workspace.id && submissionId) {
            try {
                const query = {
                    workspace_id: workspace.id,
                    submission_id: submissionId
                };
                await requestWorkspaceSubmissionDeletion(query).unwrap();
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

    const breadcrumbsItem = [
        {
            title: t(breadcrumbsItems.home),
            icon: <HomeIcon className="w-4 h-4 mr-2" />,
            onClick: () =>
                hasCustomDomain
                    ? router.push('/', undefined, {
                          scroll: true,
                          shallow: true
                      })
                    : router.push(`/${router.query.workspace_name}`, undefined, { scroll: true, shallow: true })
        },
        {
            title: t(breadcrumbsItems.submissions),
            onClick: goToSubmissions
        },
        {
            title: ['xs'].indexOf(breakpoint) !== -1 ? toEndDottedStr(form.form.formId, 10) : form.formId,
            icon: ''
        }
    ];

    const deletionStatus = !!form?.response?.deletionStatus;

    return (
        <div className="container mx-auto mt-5 flex flex-col  items-center px-6  pb-6">
            <div className="flex w-full justify-between">
                <Button variant="solid" onClick={goToSubmissions}>
                    <LongArrowLeft width={15} height={15} />
                </Button>
                <Tooltip title={deletionStatus ? t(toolTipConstant.alreadyRequestedForDeletion) : t(toolTipConstant.requestForDeletion)}>
                    <Button
                        className={`w-auto z-10 !h-10 mt-0 sm:mt-1 md:mt-3  rounded text-white ${deletionStatus ? '!bg-red-600 opacity-30' : 'bg-red-500'}  hover:!bg-red-700 hover:!-translate-y-0 focus:-translate-y-0`}
                        variant="solid"
                        onClick={handleRequestForDeletionModal}
                        disabled={!!form?.response?.deletionStatus}
                    >
                        <span className="flex gap-2 items-center">
                            <TrashIcon width={15} height={15} />
                            {/* {form?.response?.deletionStatus ? t(buttonConstant.requestedForDeletion) : t(buttonConstant.requestForDeletion)} */}
                        </span>
                    </Button>
                </Tooltip>
            </div>
            {/* <BreadcrumbsRenderer breadcrumbsItem={breadcrumbsItem} /> */}
            <div className="py-10 md:w-[700px] sm:w-[600px] w-full">
                <FormRenderer form={form.form} response={form.response} />
            </div>
        </div>
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
        console.error(err);
    }

    return {
        props: {
            ...globalProps,
            form,
            submissionId
        }
    };
}
