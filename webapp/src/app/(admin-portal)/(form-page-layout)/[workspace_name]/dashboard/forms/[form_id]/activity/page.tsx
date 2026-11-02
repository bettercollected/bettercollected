'use client';

import { useParams } from 'next/navigation';

import { ActivityGate } from '@app/components/audit-log/activity-list';

/** One form's activity: the workspace's list with the form fixed (docs/audit-log.md). The route is 404 on the server for another workspace's form. */
export default function FormActivityPage() {
    const params = useParams<{ form_id: string }>();
    const formId = Array.isArray(params?.form_id) ? params.form_id[0] : params?.form_id;
    if (!formId) return null;
    return <ActivityGate formId={formId} />;
}
