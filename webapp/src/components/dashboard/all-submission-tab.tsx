import React, { useEffect, useState } from 'react';

import SubmissionsGrid from '@app/components/cards/submission-container';
import FullScreenLoader from '@app/components/ui/fullscreen-loader';
import { useGetWorkspaceAllSubmissionsQuery } from '@app/store/workspaces/api';

export default function AllSubmissionTab({ workspace_id, requested_for_deletion_only }: any) {
    const submissionsQuery = useGetWorkspaceAllSubmissionsQuery({ workspaceId: workspace_id, requestedForDeletionOly: requested_for_deletion_only }, { pollingInterval: 30000 });
    const [responseObject, setResponseObject] = useState<any>({});

    useEffect(() => {
        if (!submissionsQuery?.isLoading && !!submissionsQuery?.data) {
            const responseMapObject = convertToClientForm(submissionsQuery?.data);
            setResponseObject(responseMapObject);
        }
    }, [submissionsQuery]);

    const convertToClientForm = (formsArray: Array<any>) => {
        return formsArray.reduce(function (accumulator, value) {
            if (!accumulator[value.formId]) {
                accumulator[value.formId] = {
                    title: value.formTitle,
                    responses: [value]
                };
            } else {
                accumulator[value.formId].responses.push(value);
            }
            return accumulator;
        }, Object.create(null));
    };

    if (submissionsQuery.isLoading) return <FullScreenLoader />;

    return (
        <>
            <SubmissionsGrid responseObject={responseObject} />
        </>
    );
}
