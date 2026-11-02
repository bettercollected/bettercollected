import Link from 'next/link';

import { useTranslation } from 'react-i18next';

import FormSettingsTab, { GroupHeading, SettingRow } from '@app/components/dashboard/form-settings';
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

/** A settings section of the page: sentence-case h2, one line of what it covers, then its groups of rows. */
const Section = ({ id, title, intro, children }: { id: string; title: string; intro?: string; children: React.ReactNode }) => (
    <section id={id} aria-labelledby={`${id}-title`} className="flex scroll-mt-6 flex-col gap-2">
        <h2 id={`${id}-title`} className="text-black-900 text-xl font-semibold">
            {title}
        </h2>
        {intro && <p className="text-black-700 max-w-[62ch] text-sm leading-relaxed">{intro}</p>}
        <div className="mt-2 flex flex-col gap-8">{children}</div>
    </section>
);

/**
 * The Settings tab hosts everything about how the form behaves and who can
 * see it, in sections that follow the creator's questions: Access (who can
 * see it, who must prove who they are), Availability (when it takes answers),
 * Respondent experience, the automations, and Advanced (original form,
 * privacy, delete). Visibility and Integrations were separate top-level tabs
 * before — the tab bar overflowed and hid entire features.
 */
export default function FormSettings() {
    const { t } = useTranslation();
    const form = useAppSelector(selectForm);
    const { openModal } = useModal();
    const workspace = useAppSelector(selectWorkspace);
    const { can, isLoading } = useWorkspacePermissions();

    // Settings change the form (form.edit); the tab is hidden without it.
    if (!isLoading && !can(WorkspacePermission.FORM_EDIT)) {
        return <p className="body4 text-black-700 py-6">{t(memberRoles.noAccess)}</p>;
    }

    const isSelf = form?.settings?.provider === 'self';
    // The builder is where purpose, retention and the privacy link are written (same rule as the header's Edit button).
    const canOpenBuilder = isSelf && form?.builderVersion === 'v2';
    const canDelete = can(WorkspacePermission.FORM_DELETE);
    const showAdvanced = !!form?.importedFormId || canOpenBuilder || canDelete;

    return (
        <div className="flex flex-col gap-12 pb-6 md:max-w-[760px]">
            <Section id="access" title={t('STAFF.FORM_SETTINGS.ACCESS')} intro={t('STAFF.FORM_SETTINGS.ACCESS_INTRO')}>
                <div>
                    <GroupHeading>{t('STAFF.FORM_SETTINGS.ACCESS_VISIBILITY')}</GroupHeading>
                    <FormSettingsTab view="VISIBILITY" />
                </div>
                <FormSettingsTab view="ACCESS" />
            </Section>

            {isSelf && (
                <Section id="availability" title={t('STAFF.FORM_SETTINGS.AVAILABILITY')} intro={t('STAFF.FORM_SETTINGS.AVAILABILITY_INTRO')}>
                    <FormSettingsTab view="AVAILABILITY" />
                </Section>
            )}

            {(isSelf || form?.isPublished) && (
                <Section id="experience" title={t('STAFF.FORM_SETTINGS.EXPERIENCE')} intro={t('STAFF.FORM_SETTINGS.EXPERIENCE_INTRO')}>
                    <FormSettingsTab view="EXPERIENCE" />
                </Section>
            )}

            {/* Email, webhooks, a case system and the integration actions: one card each, their settings in side sheets. */}
            <AutomationsSection />

            {showAdvanced && (
                <Section id="advanced" title={t('STAFF.FORM_SETTINGS.ADVANCED')}>
                    {!!form?.importedFormId && <FormSettingsTab view="ORIGINAL" />}
                    {canOpenBuilder && (
                        <div>
                            <GroupHeading>{t('STAFF.FORM_SETTINGS.ADVANCED_PRIVACY')}</GroupHeading>
                            <div className="divide-black-300 flex flex-col divide-y">
                                <SettingRow title={t('STAFF.FORM_SETTINGS.PRIVACY_TITLE')} description={t('STAFF.FORM_SETTINGS.PRIVACY_DESC')}>
                                    <Link data-testid="open-builder-privacy" href={`${getEditFormURL(workspace, form)}?tab=form`} className={buttonClassName({ variant: 'v2Button' })}>
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
                                    <div className="text-black-900 text-[15px] font-semibold">{t('STAFF.FORM_SETTINGS.DELETE_TITLE')}</div>
                                    <div className="text-black-700 text-sm leading-relaxed">
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
            )}
        </div>
    );
}
