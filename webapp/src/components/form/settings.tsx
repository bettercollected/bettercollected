import Link from 'next/link';

import { useTranslation } from 'react-i18next';

import FormSettingsTab, { GroupHeading, SettingRow } from '@app/components/dashboard/form-settings';
import { FormFileCard, PromotedFromLine } from '@app/components/form-promotion/form-file-card';
import FormAccessCard from '@app/components/form/access/form-access-card';
import AutomationsSection from '@app/components/form/automations/automations-section';
import { useModal } from '@app/components/modal-views/context';
import { memberRoles } from '@app/constants/locales/member-roles';
import { useWorkspacePermissions } from '@app/lib/hooks/use-workspace-permissions';
import { WorkspacePermission } from '@app/models/enums/workspace-permission';
import { Button, buttonClassName } from '@app/shadcn/components/ui/button';
import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { getEditFormURL } from '@app/utils/url-utils';

import { SettingsPageKey } from './settings-pages';

/** A settings section of the page: sentence-case h2, one line of what it covers, then its groups of rows. */
const Section = ({ id, title, intro, children }: { id: string; title: string; intro?: string; children: React.ReactNode }) => (
    <section id={id} aria-labelledby={`${id}-title`} className="flex scroll-mt-6 flex-col gap-2">
        <h2 id={`${id}-title`} tabIndex={-1} className="text-xl font-semibold text-black-900">
            {title}
        </h2>
        {intro && <p className="max-w-[62ch] text-sm leading-relaxed text-black-700">{intro}</p>}
        <div className="mt-2 flex flex-col gap-8">{children}</div>
    </section>
);

/**
 * One page of a form's Settings (`/settings/<page>`): Access (who can see it, who must prove who they are),
 * Availability (when it takes answers), Respondent experience, the automations, or Advanced (original form,
 * privacy, delete). Which pages exist for a form is `settingsPages`; the page heading is an h2 that takes focus
 * when the viewer arrives from another page (see the settings layout).
 */
export default function FormSettingsPage({ page }: { page: SettingsPageKey }) {
    const { t } = useTranslation();
    const { can, isLoading } = useWorkspacePermissions();

    // Settings change the form (form.edit); the menu hides them without it.
    if (!isLoading && !can(WorkspacePermission.FORM_EDIT)) {
        return <p className="body4 py-6 text-black-700">{t(memberRoles.noAccess)}</p>;
    }

    return (
        <div className="flex flex-col gap-12 pb-6 md:max-w-[760px]">
            {page === 'access' && <AccessPage />}
            {page === 'availability' && <AvailabilityPage />}
            {page === 'experience' && <ExperiencePage />}
            {/* Email, webhooks, a case system and the integration actions: one card each, their settings in side sheets. */}
            {page === 'automations' && <AutomationsSection />}
            {page === 'advanced' && <AdvancedPage />}
        </div>
    );
}

function AccessPage() {
    const { t } = useTranslation();
    // While the server has form-level access on, the page has two questions: which of your team opens the form in the
    // dashboard (the card), and who can see it as a respondent (the existing visibility). Their headings say which.
    const { formAccessEnabled } = useWorkspacePermissions();
    return (
        <Section id="access" title={t('STAFF.FORM_SETTINGS.ACCESS')} intro={t('STAFF.FORM_SETTINGS.ACCESS_INTRO')}>
            {formAccessEnabled && <FormAccessCard />}
            <div>
                <GroupHeading>{formAccessEnabled ? t('STAFF.FORM_ACCESS.RESPONDENTS_TITLE') : t('STAFF.FORM_SETTINGS.ACCESS_VISIBILITY')}</GroupHeading>
                {formAccessEnabled && <p className="max-w-[62ch] text-sm leading-relaxed text-black-700">{t('STAFF.FORM_ACCESS.RESPONDENTS_INTRO')}</p>}
                <FormSettingsTab view="VISIBILITY" />
            </div>
            <FormSettingsTab view="ACCESS" />
        </Section>
    );
}

function AvailabilityPage() {
    const { t } = useTranslation();
    return (
        <Section id="availability" title={t('STAFF.FORM_SETTINGS.AVAILABILITY')} intro={t('STAFF.FORM_SETTINGS.AVAILABILITY_INTRO')}>
            <FormSettingsTab view="AVAILABILITY" />
        </Section>
    );
}

function ExperiencePage() {
    const { t } = useTranslation();
    return (
        <Section id="experience" title={t('STAFF.FORM_SETTINGS.EXPERIENCE')} intro={t('STAFF.FORM_SETTINGS.EXPERIENCE_INTRO')}>
            <FormSettingsTab view="EXPERIENCE" />
        </Section>
    );
}

function AdvancedPage() {
    const { t, i18n } = useTranslation();
    const form = useAppSelector(selectForm);
    const { openModal } = useModal();
    const workspace = useAppSelector(selectWorkspace);
    const { can, formPromotionEnabled } = useWorkspacePermissions();
    // The builder is where purpose, retention and the privacy link are written (same rule as the header's Edit button).
    const canOpenBuilder = form?.settings?.provider === 'self' && form?.builderVersion === 'v2';
    const canDelete = can(WorkspacePermission.FORM_DELETE);

    return (
        <Section id="advanced" title={t('STAFF.FORM_SETTINGS.ADVANCED')}>
            {!!form?.importedFormId && <FormSettingsTab view="ORIGINAL" />}
            {/* Copying a form to another workspace: where this one came from (editors only: the server withholds it from others) and its file. Nothing of it while the server has it off. */}
            {formPromotionEnabled && canOpenBuilder && form?.settings?.promotedFrom && <PromotedFromLine promotedFrom={form.settings.promotedFrom} language={i18n.language} />}
            {formPromotionEnabled && canOpenBuilder && workspace?.id && form?.formId && <FormFileCard workspaceId={workspace.id} formId={form.formId} />}
            {canOpenBuilder && (
                <div>
                    <GroupHeading>{t('STAFF.FORM_SETTINGS.ADVANCED_PRIVACY')}</GroupHeading>
                    <div className="flex flex-col divide-y divide-black-300">
                        <SettingRow title={t('STAFF.FORM_SETTINGS.PRIVACY_TITLE')} description={t('STAFF.FORM_SETTINGS.PRIVACY_DESC')}>
                            <Link
                                data-testid="open-builder-privacy"
                                href={`${getEditFormURL(workspace, form)}?tab=form`}
                                // the visible words first, then what they are for (the row would otherwise name the link by its title alone)
                                aria-label={`${t('STAFF.FORM_SETTINGS.PRIVACY_BUTTON')}: ${t('STAFF.FORM_SETTINGS.PRIVACY_TITLE')}`}
                                className={buttonClassName({ variant: 'v2Button' })}
                            >
                                {t('STAFF.FORM_SETTINGS.PRIVACY_BUTTON')}
                            </Link>
                        </SettingRow>
                    </div>
                </div>
            )}
            {canDelete && (
                <div>
                    <GroupHeading>{t('STAFF.FORM_SETTINGS.DANGER')}</GroupHeading>
                    <div className="flex items-start justify-between gap-6 rounded-lg border border-[#E5B9B9] p-5">
                        <div className="flex max-w-[520px] flex-col gap-1">
                            <div className="text-[15px] font-semibold text-black-900">{t('STAFF.FORM_SETTINGS.DELETE_TITLE')}</div>
                            <div className="text-sm leading-relaxed text-black-700">
                                {typeof form?.responses === 'number' && form.responses > 0 ? t('STAFF.FORM_SETTINGS.DELETE_DESC', { count: form.responses }) : t('STAFF.FORM_SETTINGS.DELETE_DESC_NONE')}
                            </div>
                        </div>
                        <Button
                            data-umami-event="Delete Form From Settings"
                            variant="danger"
                            onClick={() => {
                                openModal('DELETE_FORM_MODAL', { form, redirectToDashboard: true });
                            }}
                        >
                            {t('STAFF.FORM_SETTINGS.DELETE_BUTTON')}
                        </Button>
                    </div>
                </div>
            )}
        </Section>
    );
}
