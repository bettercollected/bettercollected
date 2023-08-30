import { useEffect } from 'react';

import { useTranslation } from 'next-i18next';
import { NextSeo } from 'next-seo';
import { useRouter } from 'next/router';

import FormRenderer from '@app/components/form/renderer/form-renderer';
import { HomeIcon } from '@app/components/icons/home';
import DashboardLayout from '@app/components/sidebar/dashboard-layout';
import FullScreenLoader from '@app/components/ui/fullscreen-loader';
import { breadcrumbsItems } from '@app/constants/locales/breadcrumbs-items';
import { metaDataTitle } from '@app/constants/locales/meta-data-title';
import { useBreakpoint } from '@app/lib/hooks/use-breakpoint';
import { getAuthUserPropsWithWorkspace } from '@app/lib/serverSideProps';
import { setForm } from '@app/store/forms/slice';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { useGetWorkspaceSubmissionQuery } from '@app/store/workspaces/api';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { toEndDottedStr } from '@app/utils/stringUtils';

export default function SubmissionDashboard(props: any) {
    const { workspace, sub_id } = props;

    const id = sub_id;

    const { isLoading, isError, data } = useGetWorkspaceSubmissionQuery({
        workspace_id: workspace?.id ?? '',
        submission_id: id
    });

    const breakpoint = useBreakpoint();
    const router = useRouter();
    const { t } = useTranslation();
    const dispatch = useAppDispatch();
    const handleRemoveSubmissionId = () => {
        router.push(router.asPath.substring(0, router.asPath.lastIndexOf('/')), undefined, {
            shallow: true
        });
    };
    const { workspaceName } = useAppSelector(selectWorkspace);

    const breadcrumbsItem = [
        {
            title: t(breadcrumbsItems.responses),
            icon: <HomeIcon className="w-4 h-4 mr-2" />,
            onClick: handleRemoveSubmissionId
        },
        {
            title: ['xs'].indexOf(breakpoint) !== -1 ? toEndDottedStr(id, 10) : id
        }
    ];

    useEffect(() => {
        if (data) {
            dispatch(setForm(data?.form));
        }
    }, [data]);
    return (
        <DashboardLayout>
            <NextSeo title={t(metaDataTitle.submissions) + ' | ' + workspaceName} noindex={true} nofollow={true} />;
            {isLoading || isError ? (
                <FullScreenLoader />
            ) : (
                <>
                    {/* TODO: For viewing individual submission fix this later */}
                    {/* <BreadcrumbRenderer breadcrumbsItem={breadcrumbsItem} /> */}
                    <FormRenderer form={data?.form} response={data?.response} preview />
                </>
            )}
        </DashboardLayout>
    );
}

export async function getServerSideProps(_context: any) {
    const props = await getAuthUserPropsWithWorkspace(_context);

    return {
        props: {
            ...props.props,
            sub_id: _context.query.id
        }
    };
}
