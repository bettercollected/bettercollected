import React from 'react';

import { FormSlug } from '@Components/Form/FormSlug';
import { useBottomSheetModal } from '@Components/Modals/Contexts/BottomSheetModalContext';
import BottomSheetModalWrapper from '@Components/Modals/ModalWrappers/BottomSheetModalWrapper';


export interface IFormCreateSlugFullModalViewProps {
    link: string;
    customSlug: string;
}

const FormCreateSlugFullModalView = ({ customSlug, link }: IFormCreateSlugFullModalViewProps) => {
    const { closeBottomSheetModal } = useBottomSheetModal();
    const handleOnSaveChanges = () => closeBottomSheetModal();

    return (
        <BottomSheetModalWrapper>
            <FormSlug customSlug={customSlug} link={link} onSave={handleOnSaveChanges} />
        </BottomSheetModalWrapper>
    );
};

export default FormCreateSlugFullModalView;