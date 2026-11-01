import { useTranslation } from 'react-i18next';

import GenericHalfModal from '@Components/common/generic-half-modal';

export default function CloseFormConfirmationModal({ closeForm }: any) {
    const { t } = useTranslation();
    return (
        <>
            <GenericHalfModal
                headerTitle={t('STAFF.MODALS.CLOSE_FORM_HEADER')}
                title={t('STAFF.MODALS.CLOSE_FORM_TITLE')}
                subTitle={t('STAFF.MODALS.CLOSE_FORM_SUB')}
                positiveText={t('STAFF.MODALS.CLOSE_FORM_HEADER')}
                negativeText={t('BUTTON.CANCEL')}
                positiveAction={closeForm}
            />
        </>
    );
}