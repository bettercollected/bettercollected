import GenericHalfModal from '@Components/Common/Modals/GenericHalfModal';

export default function CloseFormConfirmationModal({ closeForm }: any) {
    return (
        <>
            <GenericHalfModal
                headerTitle="Close form"
                title="Are you sure to close this form?"
                subTitle="After this action is complete no one will be able to respond to this form."
                positiveText="Close form"
                negativeText="Cancel"
                positiveAction={closeForm}
            />
        </>
    );
}