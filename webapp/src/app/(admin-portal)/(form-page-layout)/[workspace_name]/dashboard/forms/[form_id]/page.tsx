import { redirect } from 'next/navigation';

import { responsePageUrl } from '@app/utils/response-urls';

// A link to one response used to be `?view=Responses&sub_id=<response id>` (a
// side panel on the form's page). It now opens the response's own page. Only
// the id travels: it is URL-encoded into a path of this workspace, never used
// as a destination itself.
export default async function Page({ params, searchParams }: { params: Promise<{ workspace_name: string; form_id: string }>; searchParams: Promise<{ view?: string | string[]; sub_id?: string | string[] }> }) {
    const { workspace_name, form_id } = await params;
    const query = await searchParams;
    const view = Array.isArray(query.view) ? query.view[0] : query.view;
    const subId = Array.isArray(query.sub_id) ? query.sub_id[0] : query.sub_id;
    if (view === 'Responses' && subId) redirect(responsePageUrl(workspace_name, form_id, subId));
    redirect(`/${workspace_name}/dashboard/forms/${form_id}/preview`);
}
