import SubmissionPage from '@app/pages/submissions/[id]';
import { getServerSidePropsInClientHostWithWorkspaceName } from '@app/utils/serverSidePropsUtils';

export default SubmissionPage;

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
