import { HistoryIcon } from '../icons/history';
import { HomeIcon } from '../icons/home';
import { Logout } from '../icons/logout-icon';
import { SearchIcon } from '../icons/search';

export const menuItems = [
    {
        href: '/1/dashboard',
        name: 'Forms',
        icon: <HomeIcon className="w-[20px] h-[20px]" />
    },
    {
        href: '/1/dashboard/submissions',
        name: 'Submissions',
        icon: <HistoryIcon className="w-[20px] h-[20px]" />
    },
    {
        href: '/1/dashboard/settings',
        name: 'Settings',
        icon: <SearchIcon className="w-[20px] h-[20px]" />
    }
];
