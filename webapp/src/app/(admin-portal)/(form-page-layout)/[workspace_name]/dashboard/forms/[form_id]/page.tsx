import { redirect } from 'next/navigation';

export default async function Page({ params }: { params: Promise<{ workspace_name: string; form_id: string }> }) {
    const { workspace_name, form_id } = await params;
    redirect(`/${workspace_name}/dashboard/forms/${form_id}/preview`);
}
