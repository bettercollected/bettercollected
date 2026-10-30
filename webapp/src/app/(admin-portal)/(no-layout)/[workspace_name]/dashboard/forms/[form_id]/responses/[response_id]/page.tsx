import { Metadata } from 'next';

import ResponsePage from '@app/components/response-page/response-page';
import environments from '@app/configs/environments';
import { getWorkspaceByName } from '@app/lib/server/api';
import fetchWithCookies from '@app/utils/fetch-utils';
import { responseOrigin, responsePageTitle } from '@app/utils/response-urls';

/**
 * The tab title, "Response · <form title>", comes from here only (the page
 * does not set it again: two writers raced, and Next's streamed metadata
 * could leave plain "Response"). The form is read with the staff member's
 * own session, as the form layout above does; never the response, so the
 * title holds no respondent's email or answer (it lands in browser history).
 * Any failure gives plain "Response".
 */
export async function generateMetadata({ params }: { params: Promise<{ workspace_name: string; form_id: string }> }): Promise<Metadata> {
    const { workspace_name, form_id } = await params;
    let form: unknown = null;
    try {
        const workspace = await getWorkspaceByName(workspace_name);
        if (workspace?.id) form = await fetchWithCookies(`${environments.INTERNAL_DOCKER_API_ENDPOINT_HOST}/workspaces/${encodeURIComponent(workspace.id)}/forms/${encodeURIComponent(form_id)}`);
    } catch {
        form = null;
    }
    return { title: { absolute: responsePageTitle(form, form_id) }, robots: { index: false, follow: false } };
}

export default async function Page({ params, searchParams }: { params: Promise<{ form_id: string; response_id: string }>; searchParams: Promise<{ from?: string | string[] }> }) {
    const { form_id, response_id } = await params;
    // `?from=` names the list the page was opened from; only the fixed names count (never an address)
    const { from } = await searchParams;
    return <ResponsePage formId={form_id} responseId={response_id} origin={responseOrigin(from)} />;
}
