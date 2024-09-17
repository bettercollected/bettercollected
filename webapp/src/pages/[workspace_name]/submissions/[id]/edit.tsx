import EditFormResponse from '@app//pages/submissions/[id]/edit';
import { getServerSidePropsInClientHostWithWorkspaceName } from '@app/utils/serverSidePropsUtils';

export default EditFormResponse;

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
