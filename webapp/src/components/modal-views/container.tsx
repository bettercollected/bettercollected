import { Fragment, useEffect } from 'react';

import dynamic from 'next/dynamic';
import { useRouter } from 'next/router';

import DeleteFormModal from '@app/components/form/delete-form-modal';
import { Close } from '@app/components/icons/close';
import LogoutView from '@app/components/logout/logout-view';
import InviteMemberModal from '@app/components/modal-views/modals/invite-member-modal';
import ShareModalView from '@app/components/modal-views/modals/share-modal-view';
import UpdateTermsOfServiceAndPrivacyPolicy from '@app/components/toc-privacy-policy';
import Button from '@app/components/ui/button';
import { Dialog } from '@app/components/ui/dialog';
import { Transition } from '@app/components/ui/transition';
import UpdateWorkspaceSettings from '@app/components/workspace/update-workspace-settings';

import { MODAL_VIEW, useModal } from './context';

// dynamic imports
const LoginView = dynamic(() => import('@app/components/login/login-view'));
const ImportProviderForms = dynamic(() => import('@app/components/form-integrations/import-provider-forms'));
const RequestForDeletionView = dynamic(() => import('@app/components/submission-request-for-deletion'));

function renderModalContent(view: MODAL_VIEW | string, modalProps: any) {
    switch (view) {
        case 'LOGIN_VIEW':
            return <LoginView {...modalProps} />; // Done
        case 'UPDATE_TERMS_OF_SERVICE_AND_PRIVACY_POLICY':
            return <UpdateTermsOfServiceAndPrivacyPolicy />;
        case 'REQUEST_FOR_DELETION_VIEW':
            return <RequestForDeletionView {...modalProps} />;
        case 'IMPORT_PROVIDER_FORMS_VIEW':
            return <ImportProviderForms {...modalProps} />; // Done
        case 'LOGOUT_VIEW':
            return <LogoutView />; // Done
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
        default:
            return <></>;
    }
}

export default function ModalContainer() {
    const router = useRouter();
    const { view, isOpen, closeModal, modalProps } = useModal();

    useEffect(() => {
        // close search modal when route change
        router.events.on('routeChangeStart', closeModal);
        return () => {
            router.events.off('routeChangeStart', closeModal);
        };
    }, []);

    return (
        <Transition appear show={isOpen} as={Fragment}>
            <Dialog as="div" className="fixed inset-0 z-[2500] h-full w-full overflow-y-auto overflow-x-hidden p-4 text-center sm:p-6 lg:p-8 xl:p-10 3xl:p-12" onClose={closeModal}>
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
                    <Button size="small" color="gray" shape="circle" onClick={closeModal} className="opacity-50 hover:opacity-80 ">
                        <Close className="h-auto w-[13px]" />
                    </Button>
                </div>

                <Transition.Child as={Fragment} enter="ease-out duration-300" enterFrom="opacity-0 scale-105" enterTo="opacity-100 scale-100" leave="ease-in duration-200" leaveFrom="opacity-100 scale-100" leaveTo="opacity-0 scale-105">
                    <div data-testid="modal-view" className="relative z-50 inline-block w-full text-left align-middle md:w-fit">
                        {view && renderModalContent(view, modalProps)}
                    </div>
                </Transition.Child>
            </Dialog>
        </Transition>
    );
}
