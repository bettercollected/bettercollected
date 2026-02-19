import { redirect } from 'next/navigation';

export default async function SubmissionPage({ params }: { params: Promise<{ workspace_name: string; id: string }> }) {
    const { workspace_name, id } = await params;
    redirect(`/${workspace_name}/dashboard/submissions/${id}/form`);
}
