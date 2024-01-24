import { useTranslation } from 'next-i18next';
import { NextSeo } from 'next-seo';

import FormRenderer from '@app/components/form/renderer/form-renderer';
import DashboardLayout from '@app/components/sidebar/dashboard-layout';
import FullScreenLoader from '@app/components/ui/fullscreen-loader';
import { metaDataTitle } from '@app/constants/locales/meta-data-title';
import { getAuthUserPropsWithWorkspace } from '@app/lib/serverSideProps';
import { useAppSelector } from '@app/store/hooks';
import { useGetWorkspaceSubmissionQuery } from '@app/store/workspaces/api';
import { selectWorkspace } from '@app/store/workspaces/slice';


export default function SubmissionDashboard(props: any) {
    const { workspace, sub_id } = props;

    const { isLoading, isError, data } = useGetWorkspaceSubmissionQuery({
        workspace_id: workspace?.id ?? '',
        submission_id: sub_id
    });

    const { t } = useTranslation();
    const { workspaceName } = useAppSelector(selectWorkspace);

    return (
        <DashboardLayout>
            <NextSeo title={t(metaDataTitle.submissions) + ' | ' + workspaceName} noindex={true} nofollow={true} />;
            {isLoading || isError ? (
                <FullScreenLoader />
            ) : (
                <>
                    <FormRenderer form={data?.form} response={data?.response} isDisabled />
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