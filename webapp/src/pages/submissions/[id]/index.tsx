import React from 'react';

import { useTranslation } from 'next-i18next';
import { useRouter } from 'next/router';

import Submission from '@Components/RespondersPortal/Submission';
import { toast } from 'react-toastify';

import { useModal } from '@app/components/modal-views/context';
import FullScreenLoader from '@app/components/ui/fullscreen-loader';
import { toastMessage } from '@app/constants/locales/toast-message';
import { ToastId } from '@app/constants/toastId';
import { getGlobalServerSidePropsByDomain } from '@app/lib/serverSideProps';
import { StandardFormDto } from '@app/models/dtos/form';
import { IServerSideProps } from '@app/models/dtos/serverSideProps';
import { useGetWorkspaceSubmissionQuery, useRequestWorkspaceSubmissionDeletionMutation } from '@app/store/workspaces/api';
import { checkHasCustomDomain } from '@app/utils/serverSidePropsUtils';

interface ISubmission extends IServerSideProps {
    form: StandardFormDto;
}

export default function SubmissionPage(props: any) {
    const { workspace, submissionId, hasCustomDomain }: ISubmission = props;
    const { t } = useTranslation();

    const router = useRouter();
    const { openModal, closeModal } = useModal();

    const [requestWorkspaceSubmissionDeletion] = useRequestWorkspaceSubmissionDeletionMutation();

    const { data } = useGetWorkspaceSubmissionQuery({
        workspace_id: workspace?.id ?? '',
        submission_id: submissionId
    });

    const handleRequestForDeletion = async () => {
        if (workspace && workspace.id && submissionId) {
            try {
                const query = {
                    workspace_id: workspace.id,
                    submission_id: submissionId
                };
                await requestWorkspaceSubmissionDeletion(query);
                toast(t(toastMessage.workspaceSuccess).toString(), { toastId: ToastId.SUCCESS_TOAST, type: 'success' });
                closeModal();
            } catch (e) {
                toast(t(toastMessage.somethingWentWrong).toString(), { toastId: ToastId.ERROR_TOAST, type: 'error' });
            }
        }
    };

    const handleRequestForDeletionModal = () => {
        openModal('REQUEST_FOR_DELETION_VIEW', { handleRequestForDeletion });
    };

    const goToSubmissions = () => {
        let pathName;
        if (hasCustomDomain) {
            pathName = '/';
        } else {
            pathName = `/${router.query.workspace_name}`;
        }

        router
            .push(
                {
                    pathname: pathName,
                    query: { view: 'mySubmissions' }
                },
                undefined,
                { scroll: true, shallow: true }
            )
            .then((r) => r)
            .catch((e) => e);
    };
    if (!data) return <FullScreenLoader />;

    return <Submission hasCustomDomain={hasCustomDomain} data={data} goToSubmissions={goToSubmissions} handleRequestForDeletionModal={handleRequestForDeletionModal} />;
}

export async function getServerSideProps(_context: any) {
    const globalProps = (await getGlobalServerSidePropsByDomain(_context)).props;
    const submissionId = _context.query.id;
    const hasCustomDomain = checkHasCustomDomain(_context);
    if (!hasCustomDomain) {
        return {
            redirect: {
                permanent: false,
                destination: '/'
            }
        };
    }

    if (!globalProps.workspace?.id) {
        return {
            notFound: true
        };
    }

    return {
        props: {
            ...globalProps,
            submissionId
        }
    };
}
