import { FormDispatcher } from "@app/app/(user-portal)/(no-layout)/[workspace_name]/forms/[form_id]/_dispatcher/FormDispatcher";
import environments from "@app/configs/environments";
import fetchWithCookies from "@app/utils/fetchUtils";
import { notFound } from "next/navigation";

export default async function Layout(
    props: { children: React.ReactNode; params: Promise<{ form_id: string; workspace_name: string }> }
) {
    const { workspace_name, form_id } = await props.params;

    const {
        children
    } = props;

    const workspaceResponse = await fetch(environments.INTERNAL_DOCKER_API_ENDPOINT_HOST + '/workspaces?workspace_name=' + workspace_name, { next: { revalidate: 300 } });
    if (!workspaceResponse.ok) return notFound();
    const workspace = await workspaceResponse.json();

    const form = await fetchWithCookies(environments.INTERNAL_DOCKER_API_ENDPOINT_HOST + '/workspaces/' + workspace.id + '/forms/' + form_id + '?published=true&draft=true');

    if (!form) return notFound();

    return (
        <FormDispatcher form={form}>
            {children}
        </FormDispatcher>
    );
}