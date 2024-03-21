import { useState } from 'react';

import { ChevronDown, UserRoundPlus } from 'lucide-react';

import {
    Popover,
    PopoverContent,
    PopoverTrigger
} from '@app/shadcn/components/ui/popover';
import { cn } from '@app/shadcn/util/lib';
import { useAuthAtom } from '@app/store/jotai/auth';

export default function UserAvatarDropDown() {
    const [popOverOpen, setPopoverOpen] = useState(false);

    return (
        <Popover open={popOverOpen} onOpenChange={setPopoverOpen}>
            <PopoverTrigger className="absolute right-10 top-4">
                <div className="flex cursor-pointer  items-center rounded-full bg-black-400 p-1">
                    <UserAvatar />
                    <ChevronDown
                        className={cn(
                            ' pt-1 text-black-600 transition',
                            popOverOpen && 'rotate-180'
                        )}
                    />
                </div>
            </PopoverTrigger>
            <PopoverContent className="p2-new z-[10] mt-2 max-w-[235px] rounded-lg bg-white p-4 text-black-700 shadow-blue-hue">
                Do you wish to track your form response for future reference?
            </PopoverContent>
        </Popover>
    );
}

const UserAvatar = () => {
    const { authState } = useAuthAtom();
    if (!authState.email) {
        return (
            <UserRoundPlus className="h-7 w-7 rounded-full bg-black-500 p-1 text-white" />
        );
    }
    if (authState.profileImage) {
        return (
            <img
                className="h-8 w-8 rounded-full"
                src={authState.profileImage}
                alt={authState.email}
            />
        );
    }
    const name = authState.firstName || authState.lastName || authState.email;

    return (
        <div className="h-8 w-8 rounded-full bg-black-500 p-1 font-medium">
            {name[0]?.toUpperCase()}
        </div>
    );
};
