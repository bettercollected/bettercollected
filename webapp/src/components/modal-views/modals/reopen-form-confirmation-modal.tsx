import { useTranslation } from 'react-i18next';

import GenericHalfModal from '@Components/common/generic-half-modal';

export default function ReopenFormConfirmationModal({ reopenForm }: any) {
    const { t } = useTranslation();
    return (
        <>
            <GenericHalfModal
                headerTitle={t('STAFF.MODALS.REOPEN_FORM')}
                title={t('STAFF.MODALS.REOPEN_TITLE')}
                subTitle={t('STAFF.MODALS.REOPEN_SUB')}
                positiveText={t('STAFF.MODALS.REOPEN_FORM')}
                negativeText={t('BUTTON.CANCEL')}
                positiveAction={reopenForm}
            />
        </>
    );
}