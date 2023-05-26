import { atom, useAtom } from 'jotai';

export type MODAL_VIEW = 'UPGRADE_TO_PRO';

const modalAtom = atom({ isOpen: false, view: '', modalProps: null });

export function useUpgradeModal() {
    const [state, setState] = useAtom(modalAtom);
    const openModal = (view: MODAL_VIEW, modalProps: any = null) =>
        setState({
            ...state,
            isOpen: true,
            view,
            modalProps
        });
    const closeModal = () => {
        setState({ ...state, isOpen: false, modalProps: null, view: '' });
    };

    return {
        ...state,
        openModal,
        closeModal
    };
}
