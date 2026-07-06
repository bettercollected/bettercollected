import { redirect } from 'next/navigation';

// Visibility is a Settings section now (the standalone tab was one of the
// reasons the tab bar overflowed and hid entire features).
export default async function Page(props: { params: Promise<{ workspace_name: string; form_id: string }> }) {
    const { workspace_name, form_id } = await props.params;
    redirect(`/${workspace_name}/dashboard/forms/${form_id}/settings`);
}
