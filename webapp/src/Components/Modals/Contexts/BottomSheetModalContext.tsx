import { useBaseModal } from '@Components/Modals/Contexts/UseBaseModal';
import { atom } from 'jotai';

export type BOTTOM_SCREEN_MODALS = 'DELETE_ACCOUNT' | 'CREATE_GROUP' | 'SELECT_GROUP_FULL_MODAL_VIEW' | 'WORKSPACE_SETTINGS' | 'SELECT_FORM_CLOSE_DATE' | 'TEMPLATE_SETTINGS_FULL_MODAL_VIEW' | 'FORM_CREATE_SLUG_VIEW' | '';

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
        }, 500);
    };

    return {
        ...state,
        openBottomSheetModal,
        closeBottomSheetModal
    };
}
