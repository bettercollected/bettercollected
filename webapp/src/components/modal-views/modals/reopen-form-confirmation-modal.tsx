import GenericHalfModal from '@Components/Common/Modals/GenericHalfModal';

export default function ReopenFormConfirmationModal({ reopenForm }: any) {
    return (
        <>
            <GenericHalfModal headerTitle="Reopen form" title="Are you sure to reopen this form?" subTitle="This will reopen this form for responses." positiveText="Reopen form" negativeText="Cancel" positiveAction={reopenForm} />
        </>
    );
}
