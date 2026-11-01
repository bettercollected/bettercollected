import { useTranslation } from 'react-i18next';

import FormAnalytics from '@app/components/analytics/analytics';


export default function FormAnalyticsDashboard() {
    const { t } = useTranslation();
    return (
        <div className="mt-[5px] w-full md:max-w-[1200px]">
            <p className="sh1 text-black-800! leading-none!">{t('STAFF.FORM_ANALYTICS')}</p>
            <FormAnalytics />
        </div>
    );
}
