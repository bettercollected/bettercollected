import { redirect } from 'next/navigation';

import { portalPath } from '@app/utils/portal-path';

export default async function SubmissionUUIDIndexPage({ params }: { params: Promise<{ id: string }> }) {
    const { id } = await params;
    redirect(portalPath(null, true, 'submissions', 'uuid', id, 'form'));
}
