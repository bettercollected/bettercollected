import React from 'react';

import { useTranslation } from 'next-i18next';

import GenericHalfModal from '@Components/Common/Modals/GenericHalfModal';

import { localesCommon } from '@app/constants/locales/common';

interface IDeleteConfirmationModal {
    title: string;
    handleDelete: () => void;
    headerTitle?: string;
    positiveText?: string;
}

export default function DeleteConfirmationModal({ title, handleDelete, headerTitle = 'Delete', positiveText = 'Delete' }: IDeleteConfirmationModal) {
    const { t } = useTranslation();

    return <GenericHalfModal headerTitle={headerTitle} positiveAction={handleDelete} positiveText={positiveText} type="danger" title={title + '?'} subTitle={t(localesCommon.deleteMessage)} />;
}
