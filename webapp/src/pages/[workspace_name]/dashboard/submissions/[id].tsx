import { useRouter } from 'next/router';

import BreadcrumbRenderer from '@app/components/form/renderer/breadcrumbs-renderer';
import FormRenderer from '@app/components/form/renderer/form-renderer';
import { HomeIcon } from '@app/components/icons/home';
import SidebarLayout from '@app/components/sidebar/sidebar-layout';
import FullScreenLoader from '@app/components/ui/fullscreen-loader';
import { useBreakpoint } from '@app/lib/hooks/use-breakpoint';
import { getAuthUserPropsWithWorkspace } from '@app/lib/serverSideProps';
import { useGetWorkspaceSubmissionQuery } from '@app/store/workspaces/api';
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
    const handleRemoveSubmissionId = () => {
        router.push(router.asPath.substring(0, router.asPath.lastIndexOf('/')), undefined, {
            shallow: true
        });
    };

    const breadcrumbsItem = [
        {
            title: 'Responses',
            icon: <HomeIcon className="w-4 h-4 mr-2" />,
            onClick: handleRemoveSubmissionId
        },
        {
            title: ['xs'].indexOf(breakpoint) !== -1 ? toEndDottedStr(id, 10) : id
        }
    ];

    return (
        <SidebarLayout>
            {isLoading || isError ? (
                <FullScreenLoader />
            ) : (
                <>
                    <BreadcrumbRenderer breadcrumbsItem={breadcrumbsItem} />
                    <FormRenderer form={data?.form} response={data?.response} />
                </>
            )}
        </SidebarLayout>
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
