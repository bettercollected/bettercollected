import React from 'react';

import { useTranslation } from 'next-i18next';

import GenericHalfModal from '@Components/Common/Modals/GenericHalfModal';

import { localesCommon } from '@app/constants/locales/common';


interface IDeleteConfirmationModla {
    title: string;
    handleDelete: () => void;
    headerTitle?: string;
}

export default function DeleteConfirmationModal({ title, handleDelete, headerTitle = 'Delete' }: IDeleteConfirmationModla) {
    const { t } = useTranslation();

    return <GenericHalfModal headerTitle={headerTitle} positiveAction={handleDelete} type="danger" title={title + '?'} subTitle={t(localesCommon.deleteMessage)} />;
}