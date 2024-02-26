import SubmissionPageByUUid from '@app//pages/[workspace_name]/submissions/uuid/[id]';
import { getGlobalServerSidePropsByDomain } from '@app/lib/serverSideProps';

export default SubmissionPageByUUid;

export async function getServerSideProps(_context: any) {
    const globalProps = (await getGlobalServerSidePropsByDomain(_context)).props;
    if (!globalProps.hasCustomDomain) {
        return {
            notFound: true
        };
    }
    const submissionUUID = _context.query.id;

    return {
        props: {
            ...globalProps,
            submissionUUID: submissionUUID
        }
    };
}
