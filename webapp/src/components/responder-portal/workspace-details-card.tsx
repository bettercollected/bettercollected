import AuthAccountProfileImage from '@app/components/auth/account-profile-image';
import ActiveLink from '@app/components/ui/links/active-link';
import { localesCommon } from '@app/constants/locales/common';
import { WorkspaceDto } from '@app/models/dtos/workspace-dto';
import { Shield } from 'lucide-react';
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
                {/* The trust anchor: this portal is where every form's "view or
                    delete your response anytime" promise is kept. Say so here. */}
                <div className="mt-4 flex items-start gap-2 rounded-lg bg-[#F4F7FD] px-3 py-2.5">
                    <Shield className="mt-0.5 h-4 w-4 shrink-0 text-[#2456CC]" strokeWidth={1.8} aria-hidden="true" />
                    <span className="text-black-700 text-sm leading-snug">You can view or delete your responses to this workspace&apos;s forms anytime.</span>
                </div>
                <div className="text-new-black-600 p4-new mt-6 flex justify-between gap-6">
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
