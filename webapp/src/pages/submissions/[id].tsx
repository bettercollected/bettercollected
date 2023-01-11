import React from 'react';

import { useRouter } from 'next/router';

import BreadcrumbsRenderer from '@app/components/form/renderer/breadcrumbs-renderer';
import FormRenderer from '@app/components/form/renderer/form-renderer';
import { HomeIcon } from '@app/components/icons/home';
import FullScreenLoader from '@app/components/ui/fullscreen-loader';
import environments from '@app/configs/environments';
import { useBreakpoint } from '@app/lib/hooks/use-breakpoint';
import { getGlobalServerSidePropsByDomain } from '@app/lib/serverSideProps';
import { StandardFormDto, StandardFormQuestionDto } from '@app/models/dtos/form';
import { IServerSideProps } from '@app/models/dtos/serverSideProps';
import { useGetWorkspaceSubmissionQuery } from '@app/store/workspaces/api';
import { checkHasCustomDomain } from '@app/utils/serverSidePropsUtils';
import { toEndDottedStr } from '@app/utils/stringUtils';

interface ISubmission extends IServerSideProps {
    form: StandardFormDto;
}

export default function Submission({ workspace, submissionId }: ISubmission) {
    const router = useRouter();
    const breakpoint = useBreakpoint();

    const { isLoading, isError, data } = useGetWorkspaceSubmissionQuery({
        workspace_id: workspace?.id ?? '',
        submission_id: submissionId
    });

    const form: any = data?.payload?.content ?? [];

    if (isLoading || isError || !data) return <FullScreenLoader />;

    const goToSubmissions = () => {
        router
            .push(
                {
                    pathname: '/',
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
            onClick: () => router.push(`/`, undefined, { scroll: false, shallow: true })
        },
        {
            title: 'Submissions',
            onClick: goToSubmissions
        },
        {
            title: ['xs'].indexOf(breakpoint) !== -1 ? toEndDottedStr(form.formId, 10) : form.formId,
            icon: ''
        }
    ];

    return (
        <div className="relative container mx-auto px-6 md:px-0">
            <BreadcrumbsRenderer breadcrumbsItem={breadcrumbsItem} />
            <FormRenderer form={form} />
        </div>
    );
}

export async function getServerSideProps(_context: any) {
    const globalProps = (await getGlobalServerSidePropsByDomain(_context)).props;
    let form: StandardFormDto | null = null;
    const { cookies } = _context.req;
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

    const auth = !!cookies.Authorization ? `Authorization=${cookies.Authorization}` : '';
    const refresh = !!cookies.RefreshToken ? `RefreshToken=${cookies.RefreshToken}` : '';

    const config = {
        method: 'GET',
        headers: {
            cookie: `${auth};${refresh}`
        }
    };

    try {
        if (globalProps.hasCustomDomain && globalProps.workspaceId) {
            const formResponse = await fetch(`${environments.API_ENDPOINT_HOST}/workspaces/${globalProps.workspaceId}/submissions/${submissionId}`, config).catch((e) => e);
            form = (await formResponse?.json().catch((e: any) => e))?.payload?.content ?? null;
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
