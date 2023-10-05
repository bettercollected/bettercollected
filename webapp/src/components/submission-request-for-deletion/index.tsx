import React from 'react';

import { useTranslation } from 'next-i18next';

import GenericHalfModal from '@Components/Common/Modals/GenericHalfModal';

import { formConstant } from '@app/constants/locales/form';

export default function RequestForDeletionView(props: any) {
    const { handleRequestForDeletion } = props;
    const { t } = useTranslation();
    return <GenericHalfModal type="danger" headerTitle="Request for Deletion" title={t(formConstant.deletionResponseWarningMessage)} positiveAction={handleRequestForDeletion} positiveText="Yes" negativeText="No" />;
}
