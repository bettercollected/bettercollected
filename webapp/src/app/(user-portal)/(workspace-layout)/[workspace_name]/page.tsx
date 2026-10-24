import { redirect } from 'next/navigation';

import { portalPath } from '@app/utils/portal-path';
import { respondentLangQuery } from '@app/utils/respondent-lang-query';

export default async function WorkspaceIndexPage({ params, searchParams }: { params: Promise<{ workspace_name: string }>; searchParams: Promise<{ lang?: string | string[] }> }) {
    const { workspace_name } = await params;
    // A respondent's ?lang=nl|en survives the redirect; nothing else does.
    const { lang } = await searchParams;
    redirect(`${portalPath(workspace_name, false, 'forms')}${respondentLangQuery(lang)}`);
}
