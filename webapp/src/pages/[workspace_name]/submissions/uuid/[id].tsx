import { getServerSidePropsInClientHostWithWorkspaceName } from '@app/utils/serverSidePropsUtils';

export default function SubmissionPageByUUid(props: any) {
    const { submissionUUID } = props;
    return <></>;
}

export async function getServerSideProps(_context: any) {
    const globalProps = (await getServerSidePropsInClientHostWithWorkspaceName(_context)).props;
    const submissionUUID = _context.query.id;
    return {
        props: {
            ...globalProps,
            submissionUUID: submissionUUID
        }
    };
}
