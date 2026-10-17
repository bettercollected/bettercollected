import { useState } from 'react';

import Link from 'next/link';
import { useRouter } from 'next/navigation';

import { SwitchIcon } from '@Components/icons/switch-icon';
import { ChevronDown, UserRoundPlus } from 'lucide-react';

import useRespondentLanguage from '@app/lib/hooks/use-respondent-language';
import { UserStatus } from '@app/models/dtos/user-status';
import { Popover, PopoverContent, PopoverTrigger } from '@app/shadcn/components/ui/popover';
import { cn } from '@app/shadcn/util/lib';
import { selectAuth } from '@app/store/auth/slice';
import { useAppSelector } from '@app/store/hooks';
import { useLazyLogOutQuery } from '@app/store/redux/form-api';

/**
 * The respondent's account control. `inline` puts it in the flow (the
 * organisation logo strip's row) instead of pinned to the page's top corner.
 */
export default function UserAvatarDropDown({ responderSignInUrl = '', disabled = false, inline = false }: { responderSignInUrl?: string; disabled?: boolean; inline?: boolean }) {
    const [popOverOpen, setPopoverOpen] = useState(false);
    const authState = useAppSelector(selectAuth);
    const { t } = useRespondentLanguage();

    return (
        <Popover open={popOverOpen} onOpenChange={setPopoverOpen}>
            {/* Pinned to the form's side gutter (form-column.ts); the welcome
                and ending pages leave room for it above their titles. */}
            <PopoverTrigger className={inline ? 'relative z-10 shrink-0' : 'absolute top-4 right-5 z-10 sm:right-8'} aria-label={t('ACCOUNT.LABEL')} data-testid="account-control">
                <div className={cn('flex cursor-pointer items-center rounded-full p-1 transition', popOverOpen ? 'bg-black-400' : 'bg-white/50')}>
                    <UserAvatar authState={authState} />
                    <ChevronDown className={cn('pt-1 text-black-600 transition', !disabled && popOverOpen && 'rotate-180')} />
                </div>
            </PopoverTrigger>
            {!disabled && (
                <PopoverContent className="p2-new z-[10] mt-2 max-w-[270px] cursor-pointer rounded border border-black-300 bg-white p-4 text-black-700 shadow-large">
                    {authState?.id ? (
                        <SwitchUserComponent authState={authState} responderSignInUrl={responderSignInUrl}></SwitchUserComponent>
                    ) : (
                        <span>
                            {t('ACCOUNT.TRACK')} <br />
                            <span>
                                <Link href={responderSignInUrl} className="text-blue-500">
                                    {t('ACCOUNT.SIGN_IN')}
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
    const { t } = useRespondentLanguage();
    const handleSwitchAccount = () => {
        responderSignInUrl && trigger('').then(() => router.push(responderSignInUrl));
    };

    return (
        <div className="flex flex-row items-center justify-between">
            <div className="flex flex-row items-center gap-1">
                <UserAvatar authState={authState} />
                <span className="text-xs">{authState.email}</span>
            </div>
            <button type="button" aria-label={t('ACCOUNT.SWITCH')} title={t('ACCOUNT.SWITCH')} onClick={handleSwitchAccount}>
                <SwitchIcon aria-hidden="true" />
            </button>
        </div>
    );
};

const UserAvatar = ({ authState }: { authState: UserStatus }) => {
    if (!authState.id) {
        return <UserRoundPlus className="h-7 w-7 rounded-full bg-black-500 p-1 text-white" />;
    }
    if (authState.profileImage) {
        return <img className="h-8 w-8 rounded-full" src={authState.profileImage} alt={authState.email} />;
    }
    const name = authState.firstName || authState.lastName || authState.email;

    return <div className="h-8 w-8 rounded-full bg-black-500 p-1 font-medium">{name[0]?.toUpperCase()}</div>;
};
