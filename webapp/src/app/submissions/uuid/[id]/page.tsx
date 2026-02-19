import { redirect } from 'next/navigation';

export default async function SubmissionUUIDIndexPage({ params }: { params: Promise<{ id: string }> }) {
    const { id } = await params;
    redirect(`/submissions/uuid/${id}/form`);
}
