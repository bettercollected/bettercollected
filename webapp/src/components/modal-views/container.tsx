import { Fragment, useCallback, useEffect } from 'react';

import { useRouter } from 'next/router';

import ImportProviderForms from '@app/components/form-integrations/import-provider-forms';
import DeleteFormModal from '@app/components/form/delete-form-modal';
import { Close } from '@app/components/icons/close';
import LogoutView from '@app/components/logout/logout-view';
import { MODAL_VIEW, useModal } from '@app/components/modal-views/context';
import CustomizeUrlModal from '@app/components/modal-views/modals/customize-url-modal';
import DeleteCustomDomainModal from '@app/components/modal-views/modals/delete-custom-domain-modal';
import DeleteInvitationModal from '@app/components/modal-views/modals/delete-invitation-modal';
import DeleteMemberModal from '@app/components/modal-views/modals/delete-member-modal';
import DeleteResponseModal from '@app/components/modal-views/modals/delete-response-modal';
import FormBuilderAddFieldModal from '@app/components/modal-views/modals/form-builder-add-field-modal';
import InviteMemberModal from '@app/components/modal-views/modals/invite-member-modal';
import ShareModalView from '@app/components/modal-views/modals/share-modal-view';
import UpdateWorkspaceSettings from '@app/components/modal-views/modals/update-workspace-settings';
import UpgradeToProModal from '@app/components/modal-views/modals/upgrade-to-pro-modal';
import RequestForDeletionView from '@app/components/submission-request-for-deletion';
import Button from '@app/components/ui/button';
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
import UserDeletionModal from './modals/user-deletion-modal';

function renderModalContent(view: MODAL_VIEW, modalProps: any) {
    switch (view) {
        case 'REQUEST_FOR_DELETION_VIEW':
            return <RequestForDeletionView {...modalProps} />;
        case 'IMPORT_PROVIDER_FORMS_VIEW':
            return <ImportProviderForms {...modalProps} />; // Done
        case 'LOGOUT_VIEW':
            return <LogoutView {...modalProps} />; // Done
        case 'SHARE_VIEW':
            return <ShareModalView {...modalProps} />; // Done
        case 'UPDATE_WORKSPACE_DOMAIN':
            return <UpdateWorkspaceSettings updateDomain={true} />;
        case 'UPDATE_WORKSPACE_HANDLE':
            return <UpdateWorkspaceSettings updateDomain={false} />;
        case 'DELETE_FORM_MODAL':
            return <DeleteFormModal {...modalProps} />; // Done
        case 'INVITE_MEMBER':
            return <InviteMemberModal />;
        case 'DELETE_MEMBER':
            return <DeleteMemberModal {...modalProps} />;
        case 'DELETE_INVITATION':
            return <DeleteInvitationModal {...modalProps} />;
        case 'CUSTOMIZE_URL':
            return <CustomizeUrlModal {...modalProps} />;
        case 'CROP_IMAGE':
            return <CropImageModalView {...modalProps} />;
        case 'DELETE_CUSTOM_DOMAIN':
            return <DeleteCustomDomainModal />;
        case 'UPGRADE_TO_PRO':
            return <UpgradeToProModal />;
        case 'EDIT_WORKSPACE_MODAL':
            return <EditWorkspaceModal />;
        case 'ADD_MEMBERS':
            return <AddMembersModal {...modalProps} />;
        case 'DELETE_CONFIRMATION':
            return <DeleteConfirmationModal {...modalProps} />;
        case 'USER_DELETION':
            return <UserDeletionModal {...modalProps} />;
        case 'ADD_GROUP_FORM':
            return <AddGroupOnForm {...modalProps} />;
        case 'ADD_FORM_GROUP':
            return <AddFormOnGroup {...modalProps} />;
        case 'ADD_REGEX':
            return <AddRegexModal {...modalProps} />;
        case 'DELETE_RESPONSE':
            return <DeleteResponseModal {...modalProps} />;
        case 'FORM_BUILDER_ADD_FIELD_VIEW':
            return <FormBuilderAddFieldModal {...modalProps} />;
        case 'FORM_BUILDER_SPOTLIGHT_VIEW':
            return <FormBuilderSpotlightModal {...modalProps} />;
        case 'FORM_BUILDER_TIPS_MODAL_VIEW':
            return <FormBuilderTipsModalView {...modalProps} />;
        case 'CONSENT_PURPOSE_MODAL_VIEW':
            return <ConsentPurposeModalView />;
        case 'CONSENT_CONFIRMATION_MODAL_VIEW':
            return <ConsentConfirmationModalView {...modalProps} />;
        case 'CONSENT_BUILDER_CONFIRMATION_MODAL_VIEW':
            return <ConsentBuilderConfirmationModalView {...modalProps} />;
        case 'CONSENT_RETENTION_MODAL_VIEW':
            return <ConsentRetentionModalView {...modalProps} />;
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
        closeModal();
    }, [closeModal, dispatch]);

    useEffect(() => {
        // close search modal when route change
        router.events.on('routeChangeStart', closeModalHandler);
        return () => {
            router.events.off('routeChangeStart', closeModalHandler);
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
                    <Button size="small" color="gray" shape="circle" onClick={closeModalHandler} className="opacity-50 hover:opacity-80 ">
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
