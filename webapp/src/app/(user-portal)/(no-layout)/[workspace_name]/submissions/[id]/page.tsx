import { redirect } from 'next/navigation';

import { portalPath } from '@app/utils/portal-path';

export default async function WorkspaceSubmissionIndexPage({ params }: { params: Promise<{ workspace_name: string, id: string }> }) {
    const { workspace_name, id } = await params;
    redirect(portalPath(workspace_name, false, 'submissions', id, 'form'));
}
