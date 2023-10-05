import React from 'react';

import { useTranslation } from 'next-i18next';

import { ButtonSize, ButtonVariant } from '@Components/Common/Input/Button/AppButtonProps';
import ModalButton from '@Components/Common/Input/Button/ModalButton';
import GenericHalfModal from '@Components/Common/Modals/GenericHalfModal';

import { Close } from '@app/components/icons/close';
import { useModal } from '@app/components/modal-views/context';
import { buttonConstant } from '@app/constants/locales/button';
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
