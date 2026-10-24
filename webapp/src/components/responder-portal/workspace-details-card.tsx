import AuthAccountProfileImage from '@app/components/auth/account-profile-image';
import ActiveLink from '@app/components/ui/links/active-link';
import { localesCommon } from '@app/constants/locales/common';
import { WorkspaceDto } from '@app/models/dtos/workspace-dto';
import useRespondentLanguage from '@app/lib/hooks/use-respondent-language';
import { useTranslation } from 'react-i18next';
import Image from 'next/image';

interface IWorkspaceDetailsCardProps {
    workspace: WorkspaceDto;
    /** In the respondent's language on the portal, in the app's on the team's dashboard. */
    audience?: 'respondent' | 'team';
}
export default function WorkspaceDetailsCard({ workspace, audience = 'team' }: IWorkspaceDetailsCardProps) {
    const { t } = useTranslation();
    const respondent = useRespondentLanguage();
    const links = audience === 'respondent' ? { terms: respondent.t('PORTAL.TERMS'), privacy: respondent.t('PORTAL.PRIVACY_POLICY'), lang: respondent.language } : { terms: t(localesCommon.termsOfServices.title), privacy: t(localesCommon.privacyPolicy.title), lang: undefined };
    return (
        <div className="border border-black-300 w-full rounded bg-white">
            {workspace.bannerImage && (
                <div className="aspect-banner relative w-full rounded-t-2xl">
                    <Image src={workspace.bannerImage} className="rounded-t-2xl" alt="" layout="fill" />
                </div>
            )}
            <div className={`${workspace.bannerImage ? 'relative left-6 top-[-36px]' : 'relative top-6 ml-6'} h-16 w-16`}>
                <AuthAccountProfileImage variant="circular" image={workspace?.profileImage} name={workspace?.title || 'U'} size={64} typography="h2" />
            </div>

            <div className={`${workspace.bannerImage ? '-mt-8' : 'mt-4'}  p-6`}>
                {/* On the portal the workspace's name is the page's one h1. */}
                {audience === 'respondent' ? <h1 className="h4-new">{workspace?.title || 'Untitled Workspace'}</h1> : <div className="h4-new">{workspace?.title || 'Untitled Workspace'}</div>}
                {workspace?.description && <div className="p2-new text-black-600 mt-1">{workspace.description}</div>}
                {/* Identity card does one job — who + policies. The
                    "view or delete anytime" promise is made actionable by the
                    tabs and the "See your submissions" card, so it no longer
                    floats here as standalone prose. */}
                <div className="text-black-600 p4-new mt-6 flex justify-between gap-6" lang={links.lang}>
                    <ActiveLink target="_blank" className="p4-new text-black-600! underline underline-offset-2 hover:text-brand-600! not-italic! leading-none!" href={workspace.termsOfService ?? `https://bettercollected.com/terms-of-service/`}>
                        {links.terms}
                    </ActiveLink>
                    <ActiveLink target="_blank" className="p4-new text-black-600! underline underline-offset-2 hover:text-brand-600! not-italic! leading-none!" href={workspace.privacyPolicy ?? `https://bettercollected.com/privacy-policy/`}>
                        {links.privacy}
                    </ActiveLink>
                </div>
            </div>
        </div>
    );
}
