import { useBaseModal } from '@Components/Modals/Contexts/UseBaseModal';
import { atom } from 'jotai';

export type BOTTOM_SCREEN_MODALS = 'WORKSPACE_SETTINGS' | '';

const modalAtom = atom<{
    isOpen: boolean;
    view: BOTTOM_SCREEN_MODALS;
    modalProps: any;
}>({ isOpen: false, modalProps: null, view: '' });

export function useBottomSheetModal() {
    const { openModal: openBottomSheetModal, closeModal, setState, ...state } = useBaseModal<BOTTOM_SCREEN_MODALS>(modalAtom);

    const closeBottomSheetModal = () => {
        setState({ ...state, view: '' });
        setTimeout(() => {
            closeModal();
        }, 400);
    };

    return {
        ...state,
        openBottomSheetModal,
        closeBottomSheetModal
    };
}