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

    const form = await fetchWithCookies(environments.INTERNAL_DOCKER_API_ENDPOINT_HOST + '/workspaces/' + workspace.id + '/forms/' + form_id + '?published=true&draft=true');

    if (!form) return notFound();

    return (
        <FormDispatcher form={form}>
            {children}
        </FormDispatcher>
    );
}