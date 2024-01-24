import { Fragment, useCallback, useEffect } from 'react';

import { useRouter } from 'next/router';

import Button from '@Components/Common/Input/Button';
import AddActionToFormModal from '@Components/Modals/DialogModals/AddActionToFormModal';
import ExportResponsesModal from '@Components/Modals/DialogModals/ExportResponsesModal';
import ImportFormModal from '@Components/Modals/DialogModals/ImportFormModal';
import OauthErrorModal from '@Components/Modals/DialogModals/OauthErrorModal';
import RedeemCouponCodeModal from '@Components/Modals/DialogModals/RedeemCouponCodeModal';
import SignInToFillFormModal from '@Components/Modals/DialogModals/SignInToFillFormModal';
import UpdateCustomDomainModal from '@Components/Modals/DialogModals/UpdateCustomDomainModal';
import UpdateWorkspaceHandle from '@Components/Modals/DialogModals/UpdateWorkspaceHandle';

import DeleteFormModal from '@app/components/form/delete-form-modal';
import { Close } from '@app/components/icons/close';
import LogoutView from '@app/components/logout/logout-view';
import { MODAL_VIEW, useModal } from '@app/components/modal-views/context';
import GenerateQRModalView from '@app/components/modal-views/modals/GenrateQRModalView';
import CloseFormConfirmationModal from '@app/components/modal-views/modals/close-form-confirmation-modal';
import CustomizeUrlModal from '@app/components/modal-views/modals/customize-url-modal';
import DeleteCustomDomainModal from '@app/components/modal-views/modals/delete-custom-domain-modal';
import DeleteInvitationModal from '@app/components/modal-views/modals/delete-invitation-modal';
import DeleteMemberModal from '@app/components/modal-views/modals/delete-member-modal';
import DeleteResponseModal from '@app/components/modal-views/modals/delete-response-modal';
import DeleteTemplateConfirmationModalView from '@app/components/modal-views/modals/delete-template-modal-view';
import FormBuilderAddFieldModal from '@app/components/modal-views/modals/form-builder-add-field-modal';
import ImportTemplateModalView from '@app/components/modal-views/modals/import-template-modal-view';
import InviteMemberModal from '@app/components/modal-views/modals/invite-member-modal';
import MobileInsertMenu from '@app/components/modal-views/modals/mobile-insert-menu';
import ReopenFormConfirmationModal from '@app/components/modal-views/modals/reopen-form-confirmation-modal';
import ShareModalView from '@app/components/modal-views/modals/share-modal-view';
import RequestForDeletionView from '@app/components/submission-request-for-deletion';
import { Dialog } from '@app/components/ui/dialog';
import { Transition } from '@app/components/ui/transition';
import { resetBuilderMenuState } from '@app/store/form-builder/actions';
import { useAppDispatch } from '@app/store/hooks';

import AddFormOnGroup from './modals/add-form-group-modal';
import AddGroupOnForm from './modals/add-group-form-modal';
import AddMembersModal from './modals/add-members-modal';
import AddRegexModal from './modals/add-regex-modal';
import ConsentBuilderConfirmationModalView from './modals/consent-builder-confirmation-modal-view';
import ConsentConfirmationModalView from './modals/consent-confirmation-modal-view';
import ConsentPurposeModalView from './modals/consent-purpose-modal-view';
import ConsentRetentionModalView from './modals/consent-retention-modal-view';
import CropImageModalView from './modals/crop-image-modal-view';
import DeleteConfirmationModal from './modals/delete-confirmation-modal';
import EditWorkspaceModal from './modals/edit-workspace-modal';
import FormBuilderSpotlightModal from './modals/form-builder-spotlight-modal';
import FormBuilderTipsModalView from './modals/form-builder-tips-modal-view';
import VisibilityConfirmationModalView from './modals/visibility-confirmation-modal-view';


function renderModalContent(view: MODAL_VIEW, modalProps: any) {
    switch (view) {
        case 'REDEEM_CODE_MODAL':
            return <RedeemCouponCodeModal {...modalProps} />;
        case 'ADD_FORM_GROUP':
            return <AddFormOnGroup {...modalProps} />;
        case 'ADD_GROUP_FORM':
            return <AddGroupOnForm {...modalProps} />;
        case 'ADD_MEMBERS':
            return <AddMembersModal {...modalProps} />;
        case 'ADD_REGEX':
            return <AddRegexModal {...modalProps} />;
        case 'CONSENT_BUILDER_CONFIRMATION_MODAL_VIEW':
            return <ConsentBuilderConfirmationModalView {...modalProps} />;
        case 'CONSENT_CONFIRMATION_MODAL_VIEW':
            return <ConsentConfirmationModalView {...modalProps} />;
        case 'CONSENT_PURPOSE_MODAL_VIEW':
            return <ConsentPurposeModalView />;
        case 'CONSENT_RETENTION_MODAL_VIEW':
            return <ConsentRetentionModalView {...modalProps} />;
        case 'CROP_IMAGE':
            return <CropImageModalView {...modalProps} />;
        case 'CUSTOMIZE_URL':
            return <CustomizeUrlModal {...modalProps} />;
        case 'DELETE_CONFIRMATION':
            return <DeleteConfirmationModal {...modalProps} />;
        case 'DELETE_CUSTOM_DOMAIN':
            return <DeleteCustomDomainModal />;
        case 'DELETE_FORM_MODAL':
            return <DeleteFormModal {...modalProps} />; // Done
        case 'DELETE_INVITATION':
            return <DeleteInvitationModal {...modalProps} />;
        case 'DELETE_MEMBER':
            return <DeleteMemberModal {...modalProps} />;
        case 'DELETE_RESPONSE':
            return <DeleteResponseModal {...modalProps} />;
        case 'EDIT_WORKSPACE_MODAL':
            return <EditWorkspaceModal />;
        case 'FORM_BUILDER_ADD_FIELD_VIEW':
            return <FormBuilderAddFieldModal {...modalProps} />;
        case 'FORM_BUILDER_SPOTLIGHT_VIEW':
            return <FormBuilderSpotlightModal {...modalProps} />;
        case 'FORM_BUILDER_TIPS_MODAL_VIEW':
            return <FormBuilderTipsModalView {...modalProps} />;
        case 'INVITE_MEMBER':
            return <InviteMemberModal />;
        case 'IMPORT_FORMS':
            return <ImportFormModal {...modalProps} />;
        case 'LOGOUT_VIEW':
            return <LogoutView {...modalProps} />; // Done
        case 'MOBILE_INSERT_MENU':
            return <MobileInsertMenu {...modalProps} />;
        case 'REQUEST_FOR_DELETION_VIEW':
            return <RequestForDeletionView {...modalProps} />;
        case 'SHARE_VIEW':
            return <ShareModalView {...modalProps} />; // Done
        case 'UPDATE_WORKSPACE_DOMAIN':
            return <UpdateCustomDomainModal />;
        case 'UPDATE_WORKSPACE_HANDLE':
            return <UpdateWorkspaceHandle {...modalProps} />;
        case 'VISIBILITY_CONFIRMATION_MODAL_VIEW':
            return <VisibilityConfirmationModalView {...modalProps} />;
        case 'CLOSE_FORM_CONFIRMATION_MODAL':
            return <CloseFormConfirmationModal {...modalProps} />;
        case 'REOPEN_FORM_CONFIRMATION_MODAL':
            return <ReopenFormConfirmationModal {...modalProps} />;
        case 'DELETE_TEMPLATE_CONFIRMATION_MODAL_VIEW':
            return <DeleteTemplateConfirmationModalView {...modalProps} />;
        case 'IMPORT_TEMPLATE_MODAL_VIEW':
            return <ImportTemplateModalView {...modalProps} />;
        case 'ADD_ACTION_TO_FORM':
            return <AddActionToFormModal {...modalProps} />;
        case 'EXPORT_RESPONSES':
            return <ExportResponsesModal {...modalProps} />;
        case 'OAUTH_ERROR_VIEW':
            return <OauthErrorModal {...modalProps} />;
        case 'GENERATE_QR':
            return <GenerateQRModalView {...modalProps} />;
        case 'SIGN_IN_TO_FILL_FORM':
            return <SignInToFillFormModal {...modalProps} />;
        default:
            return <></>;
    }
}

export default function ModalContainer() {
    const router = useRouter();
    const { view, isOpen, closeModal, modalProps } = useModal();

    const dispatch = useAppDispatch();

    const closeModalHandler = useCallback(() => {
        dispatch(resetBuilderMenuState());
        if (!modalProps?.nonClosable) closeModal();
    }, [closeModal]);

    const closeModalOnRouteChange = () => {
        dispatch(resetBuilderMenuState());
        closeModal();
    };

    useEffect(() => {
        // close search modal when route change
        router.events.on('routeChangeStart', closeModalOnRouteChange);
        return () => {
            router.events.off('routeChangeStart', closeModalOnRouteChange);
        };
    }, [closeModalHandler, router.events]);

    return (
        <Transition appear show={isOpen} as={Fragment}>
            <Dialog as="div" className="fixed inset-0 z-[2500] h-full w-full overflow-y-auto overflow-x-hidden p-4 text-center sm:p-6 lg:p-8 xl:p-10 3xl:p-12" onClose={closeModalHandler}>
                <Transition.Child as={Fragment} enter="ease-out duration-300" enterFrom="opacity-0" enterTo="opacity-100" leave="ease-in duration-200" leaveFrom="opacity-100" leaveTo="opacity-0">
                    <Dialog.Overlay className="fixed inset-0 z-40 cursor-pointer bg-gray-700 bg-opacity-60 backdrop-blur" />
                </Transition.Child>

                {/* This element is to trick the browser into centering the modal contents. */}
                {view && view !== 'SEARCH_VIEW' && (
                    <span className="inline-block h-full align-middle" aria-hidden="true">
                        &#8203;
                    </span>
                )}

                {/* This element is need to fix FocusTap headless-ui warning issue */}
                <div className="sr-only">
                    <Button size="small" onClick={closeModalHandler} className="opacity-50 hover:opacity-80 ">
                        <Close className="h-auto w-[13px]" />
                    </Button>
                </div>

                <Transition.Child as={Fragment} enter="ease-out duration-300" enterFrom="opacity-0 scale-105" enterTo="opacity-100 scale-100" leave="ease-in duration-200" leaveFrom="opacity-100 scale-100" leaveTo="opacity-0 scale-105">
                    <div data-testid="modal-view" className="relative z-50 inline-block w-full text-left align-middle md:w-fit max-h-[95vh]">
                        {
                            //@ts-ignore
                            view && renderModalContent(view, modalProps)
                        }
                    </div>
                </Transition.Child>
            </Dialog>
        </Transition>
    );
}