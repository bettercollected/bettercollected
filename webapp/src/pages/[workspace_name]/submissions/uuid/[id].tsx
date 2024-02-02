import React from 'react';

import { useTranslation } from 'next-i18next';

import Submission from '@Components/RespondersPortal/Submission';
import { toast } from 'react-toastify';

import { useModal } from '@app/components/modal-views/context';
import FullScreenLoader from '@app/components/ui/fullscreen-loader';
import { toastMessage } from '@app/constants/locales/toast-message';
import { ToastId } from '@app/constants/toastId';
import { useAppSelector } from '@app/store/hooks';
import { useGetWorkspaceSubmissionByUUIDQuery, useRequestWorkspaceSubmissionDeletionByUUIDMutation } from '@app/store/workspaces/api';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { checkHasClientDomain, getRequestHost, getServerSidePropsInClientHostWithWorkspaceName } from '@app/utils/serverSidePropsUtils';

export default function SubmissionPageByUUid(props: any) {
    const { submissionUUID, hasCustomDomain } = props;
    const workspace = useAppSelector(selectWorkspace);
    const { closeModal } = useModal();
    const { t } = useTranslation();

    const [requestForDeletionByUUID] = useRequestWorkspaceSubmissionDeletionByUUIDMutation();
    const { data } = useGetWorkspaceSubmissionByUUIDQuery(
        {
            workspace_id: workspace.id,
            submissionUUID: submissionUUID
        },
        {
            skip: !workspace.id || !submissionUUID
        }
    );

    if (!data) return <FullScreenLoader />;

    const handleRequestForDeletion = () => {
        if (workspace && workspace.id && submissionUUID) {
            const query = {
                workspace_id: workspace.id,
                submission_id: submissionUUID
            };
            requestForDeletionByUUID(query).then((response: any) => {
                if (response.data) {
                    toast(t(toastMessage.workspaceSuccess).toString(), {
                        toastId: ToastId.SUCCESS_TOAST,
                        type: 'success'
                    });
                    closeModal();
                } else if (response.error) {
                    toast('Error requesting for deletion', {
                        toastId: ToastId.SUCCESS_TOAST,
                        type: 'success'
                    });
                }
            });
        }
    };
    return <Submission hasCustomDomain={hasCustomDomain} data={data} handleRequestForDeletion={handleRequestForDeletion} />;
}

export async function getServerSideProps(_context: any) {
    const globalProps = (await getServerSidePropsInClientHostWithWorkspaceName(_context)).props;
    const hasClientDomain = checkHasClientDomain(getRequestHost(_context));
    if (!hasClientDomain) {
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
