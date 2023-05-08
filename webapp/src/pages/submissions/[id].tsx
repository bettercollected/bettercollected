import React from 'react';

import { useRouter } from 'next/router';

import BreadcrumbsRenderer from '@app/components/form/renderer/breadcrumbs-renderer';
import FormRenderer from '@app/components/form/renderer/form-renderer';
import { HomeIcon } from '@app/components/icons/home';
import { LongArrowLeft } from '@app/components/icons/long-arrow-left';
import { TrashIcon } from '@app/components/icons/trash';
import { useModal } from '@app/components/modal-views/context';
import Button from '@app/components/ui/button';
import FullScreenLoader from '@app/components/ui/fullscreen-loader';
import environments from '@app/configs/environments';
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

    const router = useRouter();
    const breakpoint = useBreakpoint();
    const { openModal } = useModal();

    const [requestWorkspaceSubmissionDeletion] = useRequestWorkspaceSubmissionDeletionMutation();

    const { isLoading, isError, data } = useGetWorkspaceSubmissionQuery({
        workspace_id: workspace?.id ?? '',
        submission_id: submissionId
    });

    const form: any = data ?? [];

    if (isLoading || isError || !data) return <FullScreenLoader />;

    const handleRequestForDeletion = async (callback: Function) => {
        if (workspace && workspace.id && submissionId) {
            const query = {
                workspace_id: workspace.id,
                submission_id: submissionId
            };
            const submission = await requestWorkspaceSubmissionDeletion(query);
        }

        if (callback && typeof callback !== undefined) {
            callback();
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
            title: 'Home',
            icon: <HomeIcon className="w-4 h-4 mr-2" />,
            onClick: () => (hasCustomDomain ? router.push('/', undefined, { scroll: true, shallow: true }) : router.push(`/${router.query.workspace_name}`, undefined, { scroll: true, shallow: true }))
        },
        {
            title: 'Submissions',
            onClick: goToSubmissions
        },
        {
            title: ['xs'].indexOf(breakpoint) !== -1 ? toEndDottedStr(form.form.formId, 10) : form.formId,
            icon: ''
        }
    ];

    const deletionStatus = !!form?.response?.deletionStatus;

    return (
        <div className="relative container mx-auto px-6 md:px-0 pb-6">
            <div className="flex justify-between">
                <Button variant="solid" className="top-3" onClick={goToSubmissions}>
                    <LongArrowLeft width={15} height={15} />
                </Button>
                <Button
                    className={`w-auto z-10 !h-10 mt-0 sm:mt-1 md:mt-3 rounded text-white ${deletionStatus ? '!bg-red-600 opacity-60' : 'bg-red-500'}  hover:!bg-red-700 hover:!-translate-y-0 focus:-translate-y-0`}
                    variant="solid"
                    onClick={handleRequestForDeletionModal}
                    disabled={!!form?.response?.deletionStatus}
                >
                    <span className="flex gap-2 items-center">
                        <TrashIcon width={15} height={15} /> {form?.response?.deletionStatus ? 'Requested ' : 'Request '}for deletion
                    </span>
                </Button>
            </div>
            {/* <BreadcrumbsRenderer breadcrumbsItem={breadcrumbsItem} /> */}
            <FormRenderer form={form.form} response={form.response} />
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
            const formResponse = await fetch(`${environments.API_ENDPOINT_HOST}/workspaces/${globalProps.workspaceId}/submissions/${submissionId}`, config).catch((e) => e);
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
