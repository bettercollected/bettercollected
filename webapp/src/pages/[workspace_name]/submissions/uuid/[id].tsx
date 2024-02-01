import React from 'react';

import Submission from '@Components/RespondersPortal/Submission';

import FullScreenLoader from '@app/components/ui/fullscreen-loader';
import { useAppSelector } from '@app/store/hooks';
import { useGetWorkspaceSubmissionByUUIDQuery } from '@app/store/workspaces/api';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { getServerSidePropsInClientHostWithWorkspaceName } from '@app/utils/serverSidePropsUtils';

export default function SubmissionPageByUUid(props: any) {
    const { submissionUUID, hasCustomDomain } = props;
    const workspace = useAppSelector(selectWorkspace);
    const { data } = useGetWorkspaceSubmissionByUUIDQuery(
        {
            workspace_id: workspace.id,
            submissionUUID: submissionUUID
        },
        {
            skip: !workspace.id || !submissionUUID
        }
    );
    console.log(data);

    if (!data) return <FullScreenLoader />;

    const handleRequestForDeletion = async () => {};

    return <Submission hasCustomDomain={hasCustomDomain} data={data} handleRequestForDeletion={handleRequestForDeletion} />;
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
