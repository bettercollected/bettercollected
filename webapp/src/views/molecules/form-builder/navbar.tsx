'use client';

import { useRouter } from 'next/navigation';

import { SheetClose } from '@app/shadcn/components/ui/sheet';

import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';
import BackButton from './back-button';

const NavBar = ({ isModal = false }: { isModal?: boolean }) => {
    const workspace = useAppSelector(selectWorkspace);
    const router = useRouter();
    const workspaceTitle = workspace?.title || workspace?.workspaceName;
    return (
        <div className="border-b-black-300 flex h-16 w-full items-center justify-start border-b-[1px] !bg-white p-4">
            {/* Workspace identity, not the product logo (de-brand decision —
                same rule as the top navbar). Still the "back to forms" target. */}
            <button
                type="button"
                aria-label={`Back to ${workspaceTitle || 'workspace'} forms`}
                className="mr-1 cursor-pointer"
                onClick={() => {
                    router.push('/' + workspace.workspaceName + '/dashboard/forms');
                }}
            >
                {workspace?.profileImage ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={workspace.profileImage} alt="" className="h-8 w-8 shrink-0 rounded-md object-cover shadow" />
                ) : (
                    <span className="bg-brand-100 text-brand-600 flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-xs font-bold shadow">{(workspaceTitle?.[0] || 'W').toUpperCase()}</span>
                )}
            </button>
            {isModal ? (
                <SheetClose asChild>
                    <div>
                        <BackButton />
                    </div>
                </SheetClose>
            ) : (
                <BackButton
                    handleClick={() => {
                        router.back();
                    }}
                />
            )}
        </div>
    );
};

export default NavBar;
