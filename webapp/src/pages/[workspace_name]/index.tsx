import DashboardContainer from '@app/containers/dashboard/DashboardContainer';
import { getGlobalServerSidePropsByWorkspaceName } from '@app/lib/serverSideProps';

export default function WorkspacePage({ workspace }: { workspace: any }) {
    return <DashboardContainer workspace={workspace} />;
}

export async function getServerSideProps(_context: any) {
    const globalProps = (await getGlobalServerSidePropsByWorkspaceName(_context)).props;
    if (!globalProps.workspace?.id) {
        return {
            notFound: true
        };
    }
    return {
        props: {
            ...globalProps,
            workspace: globalProps.workspace
        }
    };
}
