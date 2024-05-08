'use client';

import { useRouter } from 'next/navigation';

import environments from '@app/configs/environments';
import { SheetClose } from '@app/shadcn/components/ui/sheet';
import BetterCollectedSmallLogo, { NewBetterCollectedSmallLogo } from '@app/views/atoms/Icons/BetterCollectedSmallLogo';

import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';
import BackButton from './BackButton';

const NavBar = ({ isModal = false }: { isModal?: boolean }) => {
    const workspace = useAppSelector(selectWorkspace);
    const router = useRouter();
    return (
        <div className="border-b-black-300 flex h-16 w-full items-center justify-start border-b-[1px] !bg-white p-4">
            <div
                className={'bg-brand-500 active:bg-brand-600 cursor-pointer rounded-[5px] p-[6px] text-white shadow mr-1'}
                onClick={() => {
                    router.push('/' + workspace.workspaceName + '/dashboard/forms');
                }}
            >
                <NewBetterCollectedSmallLogo width={17} height={19} />
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
