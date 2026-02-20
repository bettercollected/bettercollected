import environments from '@app/configs/environments';
import { cookies } from 'next/headers';
import { notFound } from 'next/navigation';
import TemplatesClient from './TemplatesClient';

async function getPredefinedTemplates(cookieHeader: string) {
    try {
        const response = await fetch(`${environments.INTERNAL_DOCKER_API_ENDPOINT_HOST}/templates?v2=true`, {
            headers: {
                cookie: cookieHeader
            },
            cache: 'no-store'
        });
        if (!response.ok) return null;
        return await response.json();
    } catch (error) {
        console.error('Error fetching predefined templates:', error);
        return null;
    }
}

export default async function TemplatesPage({ params }: { params: Promise<{ workspace_name: string }> }) {

    const cookieStore = await cookies();
    const auth = cookieStore.get('Authorization')?.value;
    const refresh = cookieStore.get('RefreshToken')?.value;
    const cookieHeader = [
        auth ? `Authorization=${auth}` : '',
        refresh ? `RefreshToken=${refresh}` : ''
    ].filter(Boolean).join(';');

    const predefined_templates = await getPredefinedTemplates(cookieHeader);

    if (!predefined_templates) {
        notFound();
    }

    return (
        <TemplatesClient predefined_templates={predefined_templates} />
    );
}
