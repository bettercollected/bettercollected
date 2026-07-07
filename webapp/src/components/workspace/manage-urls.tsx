import { useTranslation } from 'next-i18next';

import { CustomDomainCard } from '@app/app/(admin-portal)/(side-top-nav-layout)/[workspace_name]/dashboard/custom-domain/_components/custom-domain-client';
import { useModal } from '@app/components/modal-views/context';
import { useCopyToClipboard } from '@app/lib/hooks/use-copy-to-clipboard';
import { Button } from '@app/shadcn/components/ui/button';
import { useToast } from '@app/shadcn/components/ui/use-toast';
import { selectAuth } from '@app/store/auth/slice';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { Copy, Pencil } from 'lucide-react';

/**
 * Two clearly separated sections: the workspace link responders use today
 * (with the one honest consequence of changing it), and the custom-domain
 * option. The old layout floated a "Customize Link" button mid-paragraph
 * next to a dictionary definition of "slug", 72px of dead space, and a
 * domain form free users couldn't actually use.
 */
export default function ManageURLs() {
    const { t } = useTranslation();
    const workspace = useAppSelector(selectWorkspace);
    const { toast } = useToast();
    const { openModal } = useModal();
    const auth = useAppSelector(selectAuth);

    const workspaceUrl = `${window.PUBLIC_CONFIG?.HTTP_SCHEME}${window.PUBLIC_CONFIG?.FORM_DOMAIN}/${workspace.workspaceName}`;

    const [_, copyToClipboard] = useCopyToClipboard();
    return (
        <div className="flex max-w-[720px] flex-col gap-10 pb-10">
            <section>
                <div className="h4-new mb-1">{t('WORKSPACE.SETTINGS.URLS.TITLE')}</div>
                <p className="p2-new text-black-700">{t('WORKSPACE.SETTINGS.URLS.DESCRIPTION')}</p>
                <div className="mt-4 flex flex-wrap items-center gap-3">
                    <span className="bg-black-100 text-black-800 rounded-lg px-3 py-2 font-mono text-sm">
                        {window.PUBLIC_CONFIG?.HTTP_SCHEME}
                        {window.PUBLIC_CONFIG?.FORM_DOMAIN}/<span className="font-semibold text-[#2456CC]">{workspace.workspaceName}</span>
                    </span>
                    <Button
                        data-umami-event="Copy Default Workspace Link From Workspace Setting"
                        data-umami-event-email={auth.email}
                        size="sm"
                        variant="ghost"
                        onClick={() => {
                            copyToClipboard(workspaceUrl);
                            toast({ description: 'Copied' });
                        }}
                    >
                        <Copy className="mr-2 h-4 w-4" />
                        {t('BUTTON.COPY')}
                    </Button>
                    <Button
                        data-umami-event="Customize Workspace Link"
                        data-umami-event-email={auth.email}
                        size="sm"
                        variant="v2Button"
                        onClick={() => {
                            openModal('UPDATE_WORKSPACE_HANDLE');
                        }}
                    >
                        <Pencil className="mr-2 h-4 w-4" />
                        {t('FORM_PAGE.SETTINGS.LINKS.CHANGE_SLUG')}
                    </Button>
                </div>
                {/* The consequence, stated up front — not discovered after. */}
                <p className="p4-new text-black-600 mt-2">Changing the handle changes this link; the old link stops working.</p>
            </section>
            <section>
                <CustomDomainCard />
            </section>
        </div>
    );
}
