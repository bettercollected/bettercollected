import { redirect } from 'next/navigation';

import { portalPath } from '@app/utils/portal-path';

export default async function SubmissionIndexPage({ params }: { params: Promise<{ id: string }> }) {
    const { id } = await params;
    redirect(portalPath(null, true, 'submissions', id, 'form'));
}
