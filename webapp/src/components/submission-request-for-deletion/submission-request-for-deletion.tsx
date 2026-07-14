
import { useTranslation } from 'react-i18next';

import GenericHalfModal from '@Components/common/generic-half-modal';

import { formConstant } from '@app/constants/locales/form';

export default function RequestForDeletionView(props: any) {
    const { handleRequestForDeletion } = props;
    const { t } = useTranslation();
    return (
        // Buttons say what they do — "Yes/No" makes people re-read the question.
        <GenericHalfModal
            type="danger"
            headerTitle="Request deletion"
            title={t(formConstant.deletionResponseWarningMessage)}
            subTitle="The workspace will be asked to delete this response. The request and its status stay visible to you here and under Deletion requests."
            positiveAction={handleRequestForDeletion}
            positiveText="Request deletion"
            negativeText="Cancel"
        />
    );
}
