import { HistoryIcon } from '../icons/history';
import { HomeIcon } from '../icons/home';
import { SearchIcon } from '../icons/search';

export const menuItems = [
    {
        href: '/dashboard',
        name: 'Forms',
        icon: <HomeIcon className="w-[20px] h-[20px]" />
    },
    {
        href: '/dashboard/submissions',
        name: 'Submissions',
        icon: <HistoryIcon className="w-[20px] h-[20px]" />
    },
    {
        href: '/dashboard/settings',
        name: 'Settings',
        icon: <SearchIcon className="w-[20px] h-[20px]" />
    }
];
