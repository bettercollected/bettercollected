'use client';

import { useRouter } from 'next/navigation';

import environments from '@app/configs/environments';
import { SheetClose } from '@app/shadcn/components/ui/sheet';
import BetterCollectedSmallLogo from '@app/views/atoms/Icons/BetterCollectedSmallLogo';

import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';
import BackButton from './BackButton';

const NavBar = ({ isModal = false }: { isModal?: boolean }) => {
    const workspace = useAppSelector(selectWorkspace);
    const router = useRouter();
    return (
        <div className="border-b-black-300 flex h-16 w-full items-center justify-start border-b-[1px] !bg-white p-4">
            <div className={'mr-4 cursor-pointer rounded-lg px-4 py-[6px] shadow'}>
                <BetterCollectedSmallLogo
                    onClick={() => {
                        router.push(environments.HTTP_SCHEME + environments.DASHBOARD_DOMAIN + '/' + workspace.workspaceName + '/dashboard');
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
