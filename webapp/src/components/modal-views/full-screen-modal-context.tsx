import { useBaseModal } from '@app/components/Modals/Contexts/UseBaseModal';
import { atom } from 'jotai';

export type FULL_SCREEN_MODALS =
    | ''
    | 'UPGRADE_TO_PRO'
    | 'FORM_SETTINGS_FULL_MODAL_VIEW'
    | 'FORM_CREATE_SLUG_VIEW'
    | 'SELECT_GROUP_FULL_MODAL_VIEW'
    | 'SELECT_FORM_CLOSE_DATE'
    | 'TEMPLATE_SETTINGS_FULL_MODAL_VIEW'
    | 'WORKSPACE_SETTINGS'
    | 'CREATE_GROUP'
    | 'DELETE_ACCOUNT'
    | 'VIEW_RESPONSE'
    | 'PREVIEW_MODAL';

const modalAtom = atom<{
    isOpen: boolean;
    view: FULL_SCREEN_MODALS;
    modalProps: any;
}>({ isOpen: false, modalProps: null, view: '' });

export function useFullScreenModal() {
    return useBaseModal<FULL_SCREEN_MODALS>(modalAtom);
}
