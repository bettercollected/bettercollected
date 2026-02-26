import { WorkspaceDispatcher } from "@app/app/_dispatcher/workspace-dispatcher";
import { getWorkspaceByName } from "@app/lib/server/api";
import { notFound } from "next/navigation";

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