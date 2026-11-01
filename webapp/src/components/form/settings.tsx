import { useTranslation } from 'react-i18next';

import FormSettingsTab from '@app/components/dashboard/form-settings';
import FormIntegrations from '@app/components/form/integrations';
import FormRegistrationSection from '@app/components/registration/form-registration-settings';
import FormEmailActionsSection from '@app/components/email-actions/email-actions-section';
import FormWebhooksSection from '@app/components/webhooks/webhooks-section';
import { useModal } from '@app/components/modal-views/context';
import { memberRoles } from '@app/constants/locales/member-roles';
import { formPage } from '@app/constants/locales/form-page';
import { useWorkspacePermissions } from '@app/lib/hooks/use-workspace-permissions';
import { WorkspacePermission } from '@app/models/enums/workspace-permission';
import { Button } from '@app/shadcn/components/ui/button';
import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';

/** 12px-caps section header — same rhythm as the builder's panel headers. */
const SectionHeader = ({ children }: { children: React.ReactNode }) => <h2 className="text-black-600 text-xs font-semibold uppercase tracking-wide">{children}</h2>;

/**
 * The Settings tab hosts everything about how the form behaves and who can
 * see it: general settings, visibility, integrations, and the danger zone.
 * Visibility and Integrations were separate top-level tabs before — the tab
 * bar overflowed and hid entire features.
 */
export default function FormSettings() {
    const { t } = useTranslation();
    const form = useAppSelector(selectForm);
    const { openModal } = useModal();
    const { can, isLoading } = useWorkspacePermissions();

    // Settings change the form (form.edit); the tab is hidden without it.
    if (!isLoading && !can(WorkspacePermission.FORM_EDIT)) {
        return <p className="body4 text-black-700 py-6">{t(memberRoles.noAccess)}</p>;
    }

    const showIntegrations = form?.settings?.provider === 'self' && form?.builderVersion === 'v2' && form?.isPublished;

    return (
        <div className="flex flex-col gap-12 pb-6 md:max-w-[760px]">
            <section className="flex flex-col gap-2">
                <SectionHeader>{t('STAFF.FORM_SETTINGS.GENERAL')}</SectionHeader>
                <FormSettingsTab view="DEFAULT" />
            </section>

            <section className="flex flex-col gap-2">
                <SectionHeader>{t('STAFF.FORM_SETTINGS.VISIBILITY')}</SectionHeader>
                <p className="text-black-700 text-sm">{t(formPage.visibilityDescription)}</p>
                <FormSettingsTab view="VISIBILITY" />
            </section>

            {showIntegrations && (
                <section className="flex flex-col gap-2">
                    <SectionHeader>{t('STAFF.FORM_SETTINGS.INTEGRATIONS')}</SectionHeader>
                    <FormIntegrations />
                </section>
            )}

            {/* Owners and admins, while this server sends to case systems; renders nothing otherwise. */}
            <FormRegistrationSection />

            {/* Owners and admins configure, editors see the deliveries, while this server has webhooks on; renders nothing otherwise. */}
            <FormWebhooksSection />
            {/* Mail to the form's team and a copy to the respondent, while this server has email actions on; renders nothing otherwise. */}
            <FormEmailActionsSection />

            {can(WorkspacePermission.FORM_DELETE) && (
            <section className="flex flex-col gap-2">
                <SectionHeader>{t('STAFF.FORM_SETTINGS.DANGER')}</SectionHeader>
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
            </section>
            )}
        </div>
    );
}
