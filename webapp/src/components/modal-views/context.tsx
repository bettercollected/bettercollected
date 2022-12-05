import { atom, useAtom } from 'jotai';

// export type MODAL_VIEW = 'SEARCH_VIEW' | 'SHARE_VIEW' |'LOGIN_VIEW';

export enum MODAL_VIEW {
    SEARCH_VIEW,
    SHARE_VIEW,
    LOGIN_VIEW,
    IMPORT_FORMS_VIEW
}

const modalAtom = atom({ isOpen: false, view: 'LOGIN_VIEW', modalProps: null });

export function useModal() {
    const [state, setState] = useAtom(modalAtom);
    const openModal = (view: MODAL_VIEW, modalProps: any = null) => setState({ ...state, isOpen: true, view, modalProps });
    const closeModal = () => {
        setState({ ...state, isOpen: false, modalProps: null });
    };

    return {
        ...state,
        openModal,
        closeModal
    };
}
