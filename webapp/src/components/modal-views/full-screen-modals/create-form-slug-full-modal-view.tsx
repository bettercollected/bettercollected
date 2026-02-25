
import { FormSlug } from '@app/components/Form/FormSlug';
import { useBottomSheetModal } from '@app/components/Modals/Contexts/BottomSheetModalContext';
import BottomSheetModalWrapper from '@app/components/Modals/ModalWrappers/BottomSheetModalWrapper';


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