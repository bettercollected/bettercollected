import GenericHalfModal from '@Components/common/generic-half-modal';

import useRespondentLanguage from '@app/lib/hooks/use-respondent-language';

/** The respondent confirms a deletion request for their own submission, in their language. */
export default function RequestForDeletionView(props: any) {
    const { handleRequestForDeletion } = props;
    const { t, language } = useRespondentLanguage();
    return (
        // Buttons say what they do — "Yes/No" makes people re-read the question.
        <div lang={language}>
            <GenericHalfModal
                type="danger"
                headerTitle={t('SUBMISSION.REQUEST')}
                title={t('SUBMISSION.CONFIRM_QUESTION')}
                subTitle={t('SUBMISSION.CONFIRM_TEXT')}
                positiveAction={handleRequestForDeletion}
                positiveText={t('SUBMISSION.REQUEST')}
                negativeText={t('SUBMISSION.CANCEL')}
            />
        </div>
    );
}
