import { atom, useAtom } from 'jotai';

const modalAtom = atom({ isOpen: false, modalProps: null });

export function useUpgradeModal() {
    const [state, setState] = useAtom(modalAtom);
    const openModal = (modalProps: any = null) =>
        setState({
            ...state,
            isOpen: true,
            modalProps
        });
    const closeModal = () => {
        setState({ ...state, isOpen: false, modalProps: null });
    };

    return {
        ...state,
        openModal,
        closeModal
    };
}
