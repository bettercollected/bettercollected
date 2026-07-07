import { FormDispatcher } from "@app/app/(user-portal)/(no-layout)/[workspace_name]/forms/[form_id]/_dispatcher/form-dispatcher";
import environments from "@app/configs/environments";
import { getWorkspaceByName } from "@app/lib/server/api";
import fetchWithCookies from "@app/utils/fetch-utils";
import { notFound } from "next/navigation";

export default async function Layout(
    props: { children: React.ReactNode; params: Promise<{ form_id: string; workspace_name: string }> }
) {
    const { workspace_name, form_id } = await props.params;

    const {
        children
    } = props;

    const workspace = await getWorkspaceByName(workspace_name);
    if (!workspace) return notFound();

    // The builder edits the DRAFT. With `published=true` the API returns the
    // latest published version whenever one exists (`draft=true` is only a
    // fallback for never-published forms) — so every autosaved change looked
    // lost on reload while the draft in the database was actually correct.
    const form = await fetchWithCookies(environments.INTERNAL_DOCKER_API_ENDPOINT_HOST + '/workspaces/' + workspace.id + '/forms/' + form_id);

    if (!form) return notFound();

    return (
        <FormDispatcher form={form}>
            {children}
        </FormDispatcher>
    );
}