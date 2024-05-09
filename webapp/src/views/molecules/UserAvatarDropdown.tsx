import { useState } from 'react';

import Link from 'next/link';
import { useRouter } from 'next/navigation';

import { ChevronDown, UserRoundPlus } from 'lucide-react';

import { Popover, PopoverContent, PopoverTrigger } from '@app/shadcn/components/ui/popover';
import { cn } from '@app/shadcn/util/lib';
import { UserStatus, useAuthAtom } from '@app/store/jotai/auth';
import { useLazyLogOutQuery } from '@app/store/redux/formApi';

import { SwitchIcon } from '../atoms/Icons/SwitchIcon';
import { useAppSelector } from '@app/store/hooks';
import { selectAuth } from '@app/store/auth/slice';

export default function UserAvatarDropDown({ responderSignInUrl = '', disabled = false }: { responderSignInUrl?: string; disabled?: boolean }) {
    const [popOverOpen, setPopoverOpen] = useState(false);
    const authState = useAppSelector(selectAuth);

    return (
        <Popover open={popOverOpen} onOpenChange={setPopoverOpen}>
            <PopoverTrigger className="absolute right-10 top-4">
                <div className={cn('flex cursor-pointer  items-center rounded-full p-1 transition', popOverOpen ? 'bg-black-400' : 'bg-white/50')}>
                    <UserAvatar authState={authState} />
                    <ChevronDown className={cn(' text-black-600 pt-1 transition', !disabled && popOverOpen && 'rotate-180')} />
                </div>
            </PopoverTrigger>
            {!disabled && (
                <PopoverContent className="p2-new text-black-700 shadow-blue-hue z-[10] mt-2 max-w-[270px] cursor-pointer rounded-lg bg-white p-4">
                    {authState?.id ? (
                        <SwitchUserComponent authState={authState} responderSignInUrl={responderSignInUrl}></SwitchUserComponent>
                    ) : (
                        <span>
                            Do you wish to track your form response for future reference? <br />
                            <span>
                                <Link href={responderSignInUrl} className="text-blue-500 ">
                                    Sign In
                                </Link>
                            </span>
                        </span>
                    )}
                </PopoverContent>
            )}
        </Popover>
    );
}

const SwitchUserComponent = ({ authState, responderSignInUrl }: { authState: UserStatus; responderSignInUrl: string }) => {
    const router = useRouter();
    const [trigger] = useLazyLogOutQuery();
    const handleSwitchAccount = () => {
        responderSignInUrl && trigger('').then(() => router.push(responderSignInUrl));
    };

    return (
        <div className="flex flex-row items-center justify-between">
            <div className="flex flex-row items-center gap-1">
                <UserAvatar authState={authState} />
                <span className="text-xs">{authState.email}</span>
            </div>
            <SwitchIcon onClick={handleSwitchAccount} />
        </div>
    );
};

const UserAvatar = ({ authState }: { authState: UserStatus }) => {
    if (!authState.id) {
        return <UserRoundPlus className="bg-black-500 h-7 w-7 rounded-full p-1 text-white" />;
    }
    if (authState.profileImage) {
        return <img className="h-8 w-8 rounded-full" src={authState.profileImage} alt={authState.email} />;
    }
    const name = authState.firstName || authState.lastName || authState.email;

    return <div className="bg-black-500 h-8 w-8 rounded-full p-1 font-medium">{name[0]?.toUpperCase()}</div>;
};
