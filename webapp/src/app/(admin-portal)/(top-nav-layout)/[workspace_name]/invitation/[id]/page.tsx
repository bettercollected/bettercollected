import { redirect } from 'next/navigation';

/**
 * The emailed invitation URL is scoped to the admin frontend workspace route.
 * Redirect it to the shared invitation screen while preserving that workspace
 * handle for the backend invitation request.
 */
export default async function LegacyInvitationPage({
    params
}: {
    params: Promise<{ workspace_name: string; id: string }>;
}) {
    const { workspace_name, id } = await params;
    const searchParams = new URLSearchParams({ workspace_name });

    redirect(`/invitation/${encodeURIComponent(id)}?${searchParams.toString()}`);
}
