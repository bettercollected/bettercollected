import { WorkspaceDispatcher } from "@app/app/_dispatcher/WorkspaceDispatcher";
import { notFound } from "next/navigation";
import { getWorkspaceByName } from "../../(side-top-nav-layout)/[workspace_name]/dashboard/layout";

export default async function WorkspaceDispatcherByNameLayout({
    children,
    params
}: {
    children: React.ReactNode;
    params: Promise<{ workspace_name: string }>;
}) {
    const { workspace_name } = await params;

    const workspace = await getWorkspaceByName(workspace_name);
    if (!workspace?.id) {
        notFound();
    }

    return <WorkspaceDispatcher workspace={workspace}>{children}</WorkspaceDispatcher>;
}