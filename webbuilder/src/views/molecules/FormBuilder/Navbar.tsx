'use client';

import { useRouter } from 'next/navigation';

import environments from '@app/configs/environments';
import { SheetClose } from '@app/shadcn/components/ui/sheet';
import useWorkspace from '@app/store/jotai/workspace';
import BetterCollectedSmallLogo from '@app/views/atoms/Icons/BetterCollectedSmallLogo';

import BackButton from './BackButton';

const NavBar = ({ isModal = false }: { isModal?: boolean }) => {
    const { workspace } = useWorkspace();
    const router = useRouter();
    return (
        <div className="flex h-16 w-full items-center justify-start border-b-[1px] border-b-black-300 !bg-white p-4">
            <div className={'mr-4 cursor-pointer rounded-lg px-4 py-[6px] shadow'}>
                <BetterCollectedSmallLogo
                    onClick={() => {
                        router.push(
                            environments.NEXT_PUBLIC_HTTP_SCHEME +
                                '://' +
                                environments.NEXT_PUBLIC_DASHBOARD_DOMAIN +
                                '/' +
                                workspace.workspaceName +
                                '/dashboard'
                        );
                    }}
                />
            </div>
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
