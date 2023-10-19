import { atom, useAtom } from 'jotai';

export type MODAL_VIEW =
    | 'UPDATE_TERMS_OF_SERVICE_AND_PRIVACY_POLICY'
    | 'REQUEST_FOR_DELETION_VIEW'
    | 'SEARCH_VIEW'
    | 'SHARE_VIEW'
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
    | 'EDIT_WORKSPACE_MODAL'
    | 'ADD_MEMBERS'
    | 'DELETE_CONFIRMATION'
    | 'USER_DELETION'
    | 'ADD_FORM_GROUP'
    | 'ADD_GROUP_FORM'
    | 'ADD_REGEX'
    | 'DELETE_RESPONSE'
    | 'FORM_BUILDER_SPOTLIGHT_VIEW'
    | 'FORM_BUILDER_ADD_FIELD_VIEW'
    | 'FORM_BUILDER_TIPS_MODAL_VIEW'
    | 'CONSENT_PURPOSE_MODAL_VIEW'
    | 'CONSENT_CONFIRMATION_MODAL_VIEW'
    | 'CONSENT_BUILDER_CONFIRMATION_MODAL_VIEW'
    | 'CONSENT_RETENTION_MODAL_VIEW'
    | 'MOBILE_INSERT_MENU'
    | 'VISIBILITY_CONFIRMATION_MODAL_VIEW'
    | 'CLOSE_FORM_CONFIRMATION_MODAL'
    | 'REOPEN_FORM_CONFIRMATION_MODAL'
    | 'DELETE_TEMPLATE_CONFIRMATION_MODAL_VIEW'
    | 'IMPORT_TEMPLATE_MODAL_VIEW';

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
