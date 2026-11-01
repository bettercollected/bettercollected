
import { useTranslation } from 'react-i18next';

import GenericHalfModal from '@Components/common/generic-half-modal';

import { localesCommon } from '@app/constants/locales/common';


interface IDeleteConfirmationModal {
    title: string;
    handleDelete: () => void;
    headerTitle?: string;
    positiveText?: string;
}

export default function DeleteConfirmationModal({ title, handleDelete, headerTitle, positiveText }: IDeleteConfirmationModal) {
    const { t } = useTranslation();
    headerTitle = headerTitle ?? t('BUTTON.DELETE');
    positiveText = positiveText ?? t('BUTTON.DELETE');

    return <GenericHalfModal headerTitle={headerTitle} positiveAction={handleDelete} positiveText={positiveText} type="danger" title={title + '?'} subTitle={t(localesCommon.deleteMessage)} />;
}