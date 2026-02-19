'use client';

import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';
import FormResponsesTable from '@app/Components/datatable/form/form-responses';

export default function Page() {
    const workspace = useAppSelector(selectWorkspace);
    return (
         // @ts-ignore
        <FormResponsesTable props={{ workspace, requestForDeletion: true }} />
    );
}
