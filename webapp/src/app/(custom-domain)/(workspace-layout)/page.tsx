import { headers } from 'next/headers';
import { notFound, redirect } from 'next/navigation';

import environments from '@app/configs/environments';
import { resolveCustomDomainWorkspace } from '@app/lib/server/custom-domain';
import { respondentLangQuery } from '@app/utils/respondent-lang-query';

export default async function RootPage({ searchParams }: { searchParams: Promise<{ lang?: string | string[] }> }) {
    const headerList = await headers();
    const host = headerList.get('x-forwarded-host') || headerList.get('host') || '';

    const hasCustomDomain = host !== environments.DASHBOARD_DOMAIN && host !== environments.FORM_DOMAIN;

    if (hasCustomDomain) {
        const { workspace } = await resolveCustomDomainWorkspace();

        if (!workspace?.id) {
            notFound();
        }

        // A respondent's ?lang=nl|en survives the redirect; nothing else does.
        const { lang } = await searchParams;
        redirect(`/forms${respondentLangQuery(lang)}`);
    }

    // Special case for client domain - redirect to admin domain
    if (host === environments.FORM_DOMAIN) {
        const protocol = headerList.get('x-forwarded-proto') || 'https';
        redirect(`${protocol}://${environments.DASHBOARD_DOMAIN}`);
    }

    // Default behavior for admin domain: go to login
    redirect('/login');
}
