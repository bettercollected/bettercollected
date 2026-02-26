import Onboarding from '@app/containers/onboarding';
import { getUser } from '@app/lib/server/api';
import { redirect } from 'next/navigation';

export default async function CreateWorkspacePage() {
    const user = await getUser();

    if (!user?.roles?.includes('FORM_CREATOR') || user?.plan !== 'PRO') {
        redirect('/');
    }

    return <Onboarding createWorkspace />;
}
