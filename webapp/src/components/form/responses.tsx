import FormResponsesTable from '@Components/datatable/form-responses';

import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';

export default function FormResponses() {
    const form = useAppSelector(selectForm);
    const workspace = useAppSelector(selectWorkspace);
    const requestForDeletion = false;

    return <FormResponsesTable props={{ formId: form.formId, workspace, requestForDeletion, isSubmission: true }} />;
}
