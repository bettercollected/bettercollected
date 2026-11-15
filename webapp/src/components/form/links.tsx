
import { useTranslation } from 'react-i18next';

import FormSettingsTab from '@app/components/dashboard/form-settings';
import { FormPage } from '@app/components/form/form-page';
import { formConstant } from '@app/constants/locales/form';


export default function FormLinks() {
    const { t } = useTranslation();
    return (
        <FormPage className="gap-4">
            <p className="sh1 text-black-800! leading-none!">{t(formConstant.settings.formLink.title)}</p>
            <FormSettingsTab view="LINKS" />
        </FormPage>
    );
}