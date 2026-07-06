'use client';

import FormResponsesTable from '@Components/datatable/form-responses';
import ResponseSegments from '@app/components/form/response-segments';
import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';

export default function Page() {
    const form = useAppSelector(selectForm);
    const workspace = useAppSelector(selectWorkspace);

    return (
        <div className="mt-4 px-4 md:px-10 lg:px-28">
            <ResponseSegments />
            <FormResponsesTable props={{ formId: form.formId, workspace, requestForDeletion: true }} />
        </div>
    );
}
