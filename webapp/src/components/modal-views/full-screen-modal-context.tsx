import {atom, useAtom} from 'jotai';

export type FULL_SCREEN_MODALS =
    | 'LOGIN_VIEW'
    | 'FORM_BUILDER_PREVIEW'
    | 'CROP_IMAGE'
    | 'UPGRADE_TO_PRO'
    | 'WORKSPACE_PREVIEW'
    | 'CREATE_CONSENT_FULL_MODAL_VIEW'
    | 'CONSENT_FULL_MODAL_VIEW'
    | 'FORM_SETTINGS_FULL_MODAL_VIEW'
    | 'FORM_CREATE_SLUG_VIEW'
    | 'SELECT_GROUP_FULL_MODAL_VIEW'
    | 'SELECT_FORM_CLOSE_DATE'
    | 'TEMPLATE_SETTINGS_FULL_MODAL_VIEW'
    | 'WORKSPACE_SETTINGS'
    | 'CREATE_GROUP'
    | "DELETE_ACCOUNT";

const modalAtom = atom({isOpen: false, modalProps: null, view: ''});

export function useFullScreenModal() {
    const [state, setState] = useAtom(modalAtom);
    const openModal = (view: FULL_SCREEN_MODALS, modalProps: any = null) =>
        setState({
            ...state,
            isOpen: true,
            modalProps,
            view: view
        });
    const closeModal = () => {
        setState({...state, view: '', isOpen: false, modalProps: null});
    };

    return {
        ...state,
        openModal,
        closeModal
    };
}
