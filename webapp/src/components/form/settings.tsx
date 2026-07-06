import { useTranslation } from 'next-i18next';

import FormSettingsTab from '@app/components/dashboard/form-settings';
import FormIntegrations from '@app/components/form/integrations';
import { useModal } from '@app/components/modal-views/context';
import { formPage } from '@app/constants/locales/form-page';
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

    const showIntegrations = form?.settings?.provider === 'self' && form?.builderVersion === 'v2' && form?.isPublished;

    return (
        <div className="flex flex-col gap-12 pb-6 md:max-w-[760px]">
            <section className="flex flex-col gap-2">
                <SectionHeader>General</SectionHeader>
                <FormSettingsTab view="DEFAULT" />
            </section>

            <section className="flex flex-col gap-2">
                <SectionHeader>Visibility</SectionHeader>
                <p className="text-black-700 text-sm">{t(formPage.visibilityDescription)}</p>
                <FormSettingsTab view="VISIBILITY" />
            </section>

            {showIntegrations && (
                <section className="flex flex-col gap-2">
                    <SectionHeader>Integrations</SectionHeader>
                    <FormIntegrations />
                </section>
            )}

            <section className="flex flex-col gap-2">
                <SectionHeader>Danger zone</SectionHeader>
                <div className="flex items-start justify-between gap-6 rounded-lg border border-[#E5B9B9] p-5">
                    <div className="flex max-w-[520px] flex-col gap-1">
                        <div className="text-black-900 text-[15px] font-semibold">Delete this form</div>
                        <div className="text-black-700 text-sm leading-relaxed">
                            Permanently deletes the form{typeof form?.responses === 'number' && form.responses > 0 ? ` and all ${form.responses} responses` : ' and any responses'}. This cannot be undone.
                        </div>
                    </div>
                    <Button
                        data-umami-event="Delete Form From Settings"
                        variant="danger"
                        onClick={() => {
                            openModal('DELETE_FORM_MODAL', { form, redirectToDashboard: true });
                        }}
                    >
                        Delete form
                    </Button>
                </div>
            </section>
        </div>
    );
}
