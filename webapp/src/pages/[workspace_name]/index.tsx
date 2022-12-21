import DashboardContainer from '@app/containers/dashboard/DashboardContainer';

export default function WorkspacePage({ workspace }: { workspace: any }) {
    return <DashboardContainer workspace={workspace} />;
}

export async function getServerSideProps(_context: any) {
    return {
        props: {
            workspace: null
        }
    };
}
