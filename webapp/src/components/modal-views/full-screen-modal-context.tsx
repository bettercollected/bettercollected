import { atom, useAtom } from 'jotai';

export type UPGRADE_MODAL_VIEW = 'CROP_IMAGE' | 'UPGRADE_TO_PRO' | 'WORKSPACE_PREVIEW' | 'ADD_FIELD' | '';

const modalAtom = atom({ isOpen: false, modalProps: null, view: '' });

export function useFullScreenModal() {
    const [state, setState] = useAtom(modalAtom);
    const openModal = (view: UPGRADE_MODAL_VIEW, modalProps: any = null) =>
        setState({
            ...state,
            isOpen: true,
            modalProps,
            view: view
        });
    const closeModal = () => {
        setState({ ...state, view: '', isOpen: false, modalProps: null });
    };

    return {
        ...state,
        openModal,
        closeModal
    };
}
