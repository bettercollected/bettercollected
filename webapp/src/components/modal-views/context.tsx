import { atom, useAtom } from 'jotai';

export type MODAL_VIEW =
    | 'UPDATE_TERMS_OF_SERVICE_AND_PRIVACY_POLICY'
    | 'REQUEST_FOR_DELETION_VIEW'
    | 'SEARCH_VIEW'
    | 'SHARE_VIEW'
    | 'LOGIN_VIEW'
    | 'IMPORT_PROVIDER_FORMS_VIEW'
    | 'IMPORT_FORMS'
    | 'IMPORT_GOOGLE_FORMS_VIEW'
    | 'IMPORT_TYPE_FORMS_VIEW'
    | 'LOGOUT_VIEW'
    | 'UPDATE_WORKSPACE_DOMAIN'
    | 'UPDATE_WORKSPACE_HANDLE'
    | 'DELETE_FORM_MODAL'
    | 'INVITE_MEMBER'
    | 'DELETE_MEMBER'
    | 'DELETE_INVITATION'
    | 'CUSTOMIZE_URL'
    | 'CROP_IMAGE'
    | 'DELETE_CUSTOM_DOMAIN'
    | 'UPGRADE_TO_PRO'
    | 'EDIT_WORKSPACE_MODAL'
    | 'PREVIEW_GROUP'
    | 'ADD_MEMBER'
    | 'DELETE_CONFIRMATION'
    | 'USER_DELETION'
    | 'ADD_FORM_GROUP'
    | 'ADD_GROUP_FORM';

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
        setState({ ...state, isOpen: false, modalProps: null, view: '' });
    };

    return {
        ...state,
        openModal,
        closeModal
    };
}
