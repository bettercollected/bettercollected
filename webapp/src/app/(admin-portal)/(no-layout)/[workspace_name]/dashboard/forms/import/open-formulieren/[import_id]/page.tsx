'use client';

import React, { use } from 'react';

import ImportReport from '@app/components/open-formulieren-import/import-report';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';
import NavBar from '@app/views/molecules/form-builder/navbar';

export default function OpenFormulierenImportPage(props: { params: Promise<{ workspace_name: string; import_id: string }> }) {
    const { import_id } = use(props.params);
    const workspace = useAppSelector(selectWorkspace);
    return (
        <div className="min-h-screen bg-white">
            <NavBar />
            <div className="h-body-content overflow-auto">
                <ImportReport workspaceId={workspace?.id} workspaceName={workspace?.workspaceName} importId={import_id} />
            </div>
        </div>
    );
}
