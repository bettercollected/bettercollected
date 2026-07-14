import { Fragment, useCallback } from 'react';

import AddActionToFormModal from '@Components/modals/dialog-modals/add-action-to-form-modal';
import ImportFormModal from '@Components/modals/dialog-modals/import-form-modal';
import OauthErrorModal from '@Components/modals/dialog-modals/oauth-error-modal';
import SearchBySubmissionNumberModal from '@Components/modals/dialog-modals/search-by-submission-modal';
import UpdateCustomDomainModal from '@Components/modals/dialog-modals/update-custom-domain-modal';
import UpdateWorkspaceHandle from '@Components/modals/dialog-modals/update-workspace-handle-modal';

import DeleteFormModal from '@Components/form/delete-form-modal';
import GenerateQRModalView from '@Components/modal-views/modals/generate-qr-modal-view';
import RequestForDeletionView from '@Components/submission-request-for-deletion/submission-request-for-deletion';
import { Close } from '@app/components/icons/close';
import LogoutView from '@app/components/logout/logout-view';
import { MODAL_VIEW, useModal } from '@app/components/modal-views/context';
import CloseFormConfirmationModal from '@app/components/modal-views/modals/close-form-confirmation-modal';
import CustomizeUrlModal from '@app/components/modal-views/modals/customize-url-modal';
import DeleteCustomDomainModal from '@app/components/modal-views/modals/delete-custom-domain-modal';
import DeleteInvitationModal from '@app/components/modal-views/modals/delete-invitation-modal';
import DeleteMemberModal from '@app/components/modal-views/modals/delete-member-modal';
import DeleteResponseModal from '@app/components/modal-views/modals/delete-response-modal';
import DeleteTemplateConfirmationModalView from '@app/components/modal-views/modals/delete-template-modal-view';
import InviteMemberModal from '@app/components/modal-views/modals/invite-member-modal';
import ReopenFormConfirmationModal from '@app/components/modal-views/modals/reopen-form-confirmation-modal';
import ShareModalView from '@app/components/modal-views/modals/share-modal-view';
import { Dialog, DialogBackdrop } from '@app/components/ui/dialog';
import { Transition } from '@app/components/ui/transition';

import { Button } from '@app/shadcn/components/ui/button';
import AddFormOnGroup from './modals/add-form-group-modal';
import AddGroupOnForm from './modals/add-group-form-modal';
import AddMembersModal from './modals/add-members-modal';
import AddRegexModal from './modals/add-regex-modal';
import DeleteConfirmationModal from './modals/delete-confirmation-modal';
import EditWorkspaceModal from './modals/edit-workspace-modal';
import VisibilityConfirmationModalView from './modals/visibility-confirmation-modal-view';

function renderModalContent(view: MODAL_VIEW, modalProps: any) {
    switch (view) {
        case 'ADD_FORM_GROUP':
            return <AddFormOnGroup {...modalProps} />;
        case 'ADD_GROUP_FORM':
            return <AddGroupOnForm {...modalProps} />;
        case 'ADD_MEMBERS':
            return <AddMembersModal {...modalProps} />;
        case 'ADD_REGEX':
            return <AddRegexModal {...modalProps} />;
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
        case 'INVITE_MEMBER':
            return <InviteMemberModal />;
        case 'IMPORT_FORMS':
            return <ImportFormModal {...modalProps} />;
        case 'LOGOUT_VIEW':
            return <LogoutView {...modalProps} />; // Done
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
        case 'ADD_ACTION_TO_FORM':
            return <AddActionToFormModal {...modalProps} />;
        case 'OAUTH_ERROR_VIEW':
            return <OauthErrorModal {...modalProps} />;
        case 'GENERATE_QR':
            return <GenerateQRModalView {...modalProps} />;
        case 'SEARCH_BY_SUBMISSION_NUMBER':
            return <SearchBySubmissionNumberModal {...modalProps} />;
        default:
            return <></>;
    }
}

export default function ModalContainer() {
    const { view, isOpen, closeModal, modalProps } = useModal();

    const closeModalHandler = useCallback(() => {
        if (!modalProps?.nonClosable) closeModal();
    }, [closeModal, modalProps]);

    return (
        <Transition appear show={isOpen} as={Fragment}>
            <Dialog as="div" className="3xl:p-12 fixed inset-0 z-[2500] h-full w-full overflow-y-auto overflow-x-hidden p-4 text-center sm:p-6 lg:p-8 xl:p-10" onClose={closeModalHandler}>
                <Transition.Child as={Fragment} enter="ease-out duration-300" enterFrom="opacity-0" enterTo="opacity-100" leave="ease-in duration-200" leaveFrom="opacity-100" leaveTo="opacity-0">
                    <DialogBackdrop className="fixed inset-0 z-40 cursor-pointer bg-gray-700 bg-opacity-60 backdrop-blur" />
                </Transition.Child>

                {/* This element is to trick the browser into centering the modal contents. */}
                {view && view !== 'SEARCH_VIEW' && (
                    <span className="inline-block h-full align-middle" aria-hidden="true">
                        &#8203;
                    </span>
                )}

                {/* This element is need to fix FocusTap headless-ui warning issue */}
                <div className="sr-only">
                    <Button size="sm" onClick={closeModalHandler} className="opacity-50 hover:opacity-80 ">
                        <Close className="h-auto w-[13px]" />
                    </Button>
                </div>

                <Transition.Child as={Fragment} enter="ease-out duration-300" enterFrom="opacity-0 scale-105" enterTo="opacity-100 scale-100" leave="ease-in duration-200" leaveFrom="opacity-100 scale-100" leaveTo="opacity-0 scale-105">
                    <div data-testid="modal-view" className="relative z-50 inline-block max-h-[95vh] w-full text-left align-middle md:w-fit">
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
