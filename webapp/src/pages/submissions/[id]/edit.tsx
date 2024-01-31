import { useGetWorkspaceSubmissionQuery } from '@app/store/workspaces/api';
import { getServerSidePropsInClientHostWithWorkspaceName } from '@app/utils/serverSidePropsUtils';

export default function EditFormResponse(props: any) {
    const { workspace, submissionId } = props;

    const { isLoading, isError, data } = useGetWorkspaceSubmissionQuery({
        workspace_id: workspace?.id ?? '',
        submission_id: submissionId
    });
    return <></>;
}

export async function getServerSideProps(_context: any) {
    const globalProps = (await getServerSidePropsInClientHostWithWorkspaceName(_context)).props;
    const submissionId = _context.query.id;
    return {
        props: {
            ...globalProps,
            submissionId
        }
    };
}
