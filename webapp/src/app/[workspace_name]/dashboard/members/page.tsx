import { redirect } from 'next/navigation';

export default async function Page({ params }: { params: Promise<{ workspace_name: string }> }) {
    const { workspace_name } = await params;
    redirect(`/${workspace_name}/dashboard/members/collaborators`);
}
