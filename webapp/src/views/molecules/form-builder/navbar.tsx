'use client';

import { useRouter } from 'next/navigation';

import { useTranslation } from 'react-i18next';
import { SheetClose } from '@app/shadcn/components/ui/sheet';

import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { workspaceDisplayName } from '@app/utils/workspace-display-name';
import BackButton from './back-button';

const NavBar = ({ isModal = false }: { isModal?: boolean }) => {
    const { t } = useTranslation('builder');
    const workspace = useAppSelector(selectWorkspace);
    const router = useRouter();
    const workspaceTitle = workspaceDisplayName(workspace);
    return (
        <div className="border-b-black-300 flex h-16 w-full items-center justify-start border-b bg-white! p-4">
            {/* Workspace identity, not the product logo (de-brand decision —
                same rule as the top navbar). Still the "back to forms" target. */}
            <button
                type="button"
                aria-label={t('TOPBAR.BACK_TO', { name: workspaceTitle || t('TOPBAR.WORKSPACE') })}
                className="mr-1 cursor-pointer"
                onClick={() => {
                    router.push('/' + workspace.workspaceName + '/dashboard/forms');
                }}
            >
                {workspace?.profileImage ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={workspace.profileImage} alt="" className="h-8 w-8 shrink-0 rounded-md border border-black-300 object-cover" />
                ) : (
                    <span className="bg-brand-100 text-brand-600 flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-xs font-bold">{(workspaceTitle?.[0] || 'W').toUpperCase()}</span>
                )}
            </button>
            {isModal ? (
                <SheetClose asChild>
                    <div>
                        <BackButton label={t('BUTTON.BACK', { ns: 'common' })} />
                    </div>
                </SheetClose>
            ) : (
                <BackButton
                    label={t('BUTTON.BACK', { ns: 'common' })}
                    handleClick={() => {
                        router.back();
                    }}
                />
            )}
        </div>
    );
};

export default NavBar;
