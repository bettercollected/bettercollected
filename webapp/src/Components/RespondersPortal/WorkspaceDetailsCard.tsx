import AuthAccountProfileImage from '@app/components/auth/account-profile-image';
import ActiveLink from '@app/components/ui/links/active-link';
import { localesCommon } from '@app/constants/locales/common';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { useTranslation } from 'next-i18next';
import Image from 'next/image';

interface IWorkspaceDetailsCardProps {
    workspace: WorkspaceDto;
}
export default function WorkspaceDetailsCard({ workspace }: IWorkspaceDetailsCardProps) {
    const { t } = useTranslation();
    return (
        <div className="shadow-workspace-card w-full rounded-xl bg-white">
            {workspace.bannerImage && (
                <div className="aspect-banner relative w-full rounded-t-2xl">
                    <Image src={workspace.bannerImage} className="rounded-t-2xl" alt="Worksace Banner" layout="fill" />
                </div>
            )}
            <div className={`${workspace.bannerImage ? 'relative left-6 top-[-36px]' : 'relative top-6 ml-6'} h-16 w-16`}>
                <AuthAccountProfileImage variant="circular" image={workspace?.profileImage} name={workspace?.title || 'U'} size={64} typography="h2" />
            </div>

            <div className={`${workspace.bannerImage ? '-mt-8' : 'mt-4'}  p-6`}>
                <div className="h4-new">{workspace?.title || 'Untitled Workspace'}</div>
                {workspace?.description && <div className="p2-new text-black-600 mt-1">{workspace.description}</div>}
                <div className="text-new-black-600 p4-new mt-8 flex justify-between gap-6">
                    <ActiveLink target="_blank" className="p4-new !text-black-600 !not-italic !leading-none" href={workspace.termsOfService ?? `https://bettercollected.com/terms-of-service/`}>
                        {t(localesCommon.termsOfServices.title)}
                    </ActiveLink>
                    <ActiveLink target="_blank" className="p4-new !text-black-600 !not-italic !leading-none" href={workspace.privacyPolicy ?? `https://bettercollected.com/privacy-policy/`}>
                        {t(localesCommon.privacyPolicy.title)}
                    </ActiveLink>
                </div>
            </div>
        </div>
    );
}
