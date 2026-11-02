import { redirect } from 'next/navigation';

// Settings is five pages (see the settings layout); there is one address per page, so the bare address goes to the first.
export default async function Page(props: { params: Promise<{ workspace_name: string; form_id: string }> }) {
    const { workspace_name, form_id } = await props.params;
    redirect(`/${workspace_name}/dashboard/forms/${form_id}/settings/access`);
}
