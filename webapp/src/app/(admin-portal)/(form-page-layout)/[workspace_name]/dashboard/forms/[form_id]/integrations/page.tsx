import { redirect } from 'next/navigation';

// Integrations is a Settings section now — see visibility/page.tsx.
export default async function Page(props: { params: Promise<{ workspace_name: string; form_id: string }> }) {
    const { workspace_name, form_id } = await props.params;
    redirect(`/${workspace_name}/dashboard/forms/${form_id}/settings`);
}
