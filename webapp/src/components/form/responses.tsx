import { useEffect, useState } from 'react';

import { useTranslation } from 'react-i18next';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';


import FormResponsesTable from '@Components/datatable/form-responses';
import { useModal } from '@app/components/modal-views/context';
import { useToast } from '@app/shadcn/components/ui/use-toast';
import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { useLazyGetWorkspaceSubmissionQuery } from '@app/store/workspaces/api';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { IGetWorkspaceSubmissionQuery } from '@app/store/workspaces/types';

export default function FormResponses() {
    const router = useRouter();
    const pathname = usePathname();
    const searchParams = useSearchParams();
    const { toast } = useToast();
    let submissionId: string = (searchParams?.get('sub_id') as string) ?? '';
    const [trigger] = useLazyGetWorkspaceSubmissionQuery();
    const { t } = useTranslation();
    const form = useAppSelector(selectForm);
    const workspace = useAppSelector(selectWorkspace);
    const [submissionForm, setSubmissionForm] = useState<any>([]);
    const requestForDeletion = false;
    const { openModal } = useModal();

    useEffect(() => {
        if (!!submissionId && workspace?.id) {
            const submissionQuery: IGetWorkspaceSubmissionQuery = {
                workspace_id: workspace.id,
                submission_id: submissionId
            };
            trigger(submissionQuery)
                .then((d) => {
                    setSubmissionForm(d.data);
                })
                .catch((e) => {
                    toast({ description: 'Error fetching submission data.', variant: 'destructive' });
                });
        }
    }, [submissionId, workspace?.id]);

    return (
        <>
            {<FormResponsesTable props={{ formId: form.formId, workspace, requestForDeletion, isSubmission: true }} />}
        </>
    );
}
