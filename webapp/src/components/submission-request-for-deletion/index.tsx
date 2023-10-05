import React, { useRef } from 'react';

import { useTranslation } from 'next-i18next';

import { ButtonSize, ButtonVariant } from '@Components/Common/Input/Button/AppButtonProps';
import ModalButton from '@Components/Common/Input/Button/ModalButton';
import GenericHalfModal from '@Components/Common/Modals/GenericHalfModal';

import { Close } from '@app/components/icons/close';
import { useModal } from '@app/components/modal-views/context';
import { buttonConstant } from '@app/constants/locales/button';
import { formConstant } from '@app/constants/locales/form';

export default function RequestForDeletionView(props: any) {
    const { handleRequestForDeletion } = props;
    const { t } = useTranslation();
    return <GenericHalfModal type="danger" headerTitle="Request for Deletion" title={t(formConstant.deletionResponseWarningMessage)} positiveAction={handleRequestForDeletion} positiveText="Yes" negativeText="No" />;
}
