import { atom, useAtom } from 'jotai';

export type MODAL_VIEW = 'SEARCH_VIEW' | 'SHARE_VIEW' | 'LOGIN_VIEW' | 'IMPORT_FORMS_VIEW' | 'LOGOUT_VIEW' | 'UPDATE_WORKSPACE_DOMAIN' | 'UPDATE_WORKSPACE_HANDLE';

const modalAtom = atom({ isOpen: false, view: '', modalProps: null });

export function useModal() {
    const [state, setState] = useAtom(modalAtom);
    const openModal = (view: MODAL_VIEW, modalProps: any = null) =>
        setState({
            ...state,
            isOpen: true,
            view,
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
