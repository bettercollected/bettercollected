import { Settings } from '@mui/icons-material';

import { HistoryIcon } from '../icons/history';
import { HomeIcon } from '../icons/home';

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
        icon: <Settings className="w-[20px] h-[20px]" />
    }
];
