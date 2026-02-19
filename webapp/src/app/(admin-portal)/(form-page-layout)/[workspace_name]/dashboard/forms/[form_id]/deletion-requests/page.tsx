'use client';

import FormResponsesTable from '@app/Components/datatable/form/form-responses';
import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';

export default function Page() {
    const form = useAppSelector(selectForm);
    const workspace = useAppSelector(selectWorkspace);

    return (
        <FormResponsesTable props={{ formId: form.formId, workspace, requestForDeletion: true }} />
    );
}
