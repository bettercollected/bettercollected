
import { FormSlug } from '@Components/form/form-slug';
import { useBottomSheetModal } from '@Components/modals/contexts/bottom-sheet-modal-context';
import BottomSheetModalWrapper from '@Components/modals/modal-wrapper/bottom-sheet-modal-wrapper';


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