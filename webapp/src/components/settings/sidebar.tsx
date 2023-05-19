import { useTranslation } from 'next-i18next';
import Link from 'next/link';
import { useRouter } from 'next/router';

import { ChevronRight } from '@mui/icons-material';

import BackButton from '@app/components/settings/back';
import environments from '@app/configs/environments';
import { localesGlobal } from '@app/constants/locales/global';
import { members } from '@app/constants/locales/members';
import { workspaceConstant } from '@app/constants/locales/workspace';
import { useAppSelector } from '@app/store/hooks';

interface IMenuItemProps {
    children: any;
    active?: boolean;
    href: string;
    className?: string;
}

const MenuItem = ({ children, active = false, href, className = '' }: IMenuItemProps) => {
    const router = useRouter();

    return (
        <Link href={href}>
            <div className={`w-full body4 cursor-pointer py-5 px-4 ${router.asPath === href ? 'bg-brand-200' : ''}` + ' ' + className}>{children}</div>
        </Link>
    );
};

export function SettingsSidebar() {
    const { t } = useTranslation();
    const workspace = useAppSelector((state) => state.workspace);

    return (
        <div className="flex py-6 space-y-6 flex-col">
            <BackButton />
            <div className="paragraph text-black-800">
                <Link href={`/${workspace.workspaceName}/dashboard`}>{t(localesGlobal.dashboard)}</Link>
                <ChevronRight />
                <Link href={`${environments.HTTP_SCHEME}/${environments.CLIENT_DOMAIN}/${workspace.workspaceName}`}>{t(workspaceConstant.default)}</Link>
                <ChevronRight />
                <span>{t(localesGlobal.manage)}</span>
            </div>
            <div className="bg-white rounded flex flex-col">
                <MenuItem href={`/${workspace?.workspaceName}/manage`}>{t(localesGlobal.basicInformation)}</MenuItem>
                <MenuItem href={`/${workspace?.workspaceName}/manage/members`}>{t(members.default)}</MenuItem>
                {/*<MenuItem href={`/${workspace?.workspaceName}/manage/links`}>Links</MenuItem>*/}
                <MenuItem href={`/${workspace?.workspaceName}/manage/advanced`}>{t(localesGlobal.advance)}</MenuItem>
            </div>
        </div>
    );
}
