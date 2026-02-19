import { redirect } from 'next/navigation';

export default async function GroupPreviewPage({ params }: { params: Promise<{ workspace_name: string; group_id: string }> }) {
    const { workspace_name, group_id } = await params;
    redirect(`/${workspace_name}/dashboard/responders-groups/${group_id}/details`);
}
