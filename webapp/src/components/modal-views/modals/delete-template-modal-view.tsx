import React from 'react';

import GenericHalfModal from '@Components/Common/Modals/GenericHalfModal';

export default function DeleteTemplateConfirmationModalView({ handleDelete = () => {} }: { handleDelete: () => void }) {
    return (
        <GenericHalfModal
            headerTitle="Delete Form Template"
            positiveAction={handleDelete}
            positiveText="Delete"
            type="danger"
            title={'Are You Sure To Delete This Template?'}
            subTitle={'Once the creator deletes your response, it will be permanently removed.'}
        />
    );
}
