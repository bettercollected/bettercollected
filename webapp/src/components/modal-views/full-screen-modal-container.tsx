import { Fragment, useCallback, useEffect } from 'react';

import { useRouter } from 'next/router';

import { Button } from '@mui/material';

import { Close } from '@app/components/icons/close';
import LoginView from '@app/components/login/login-view';
import ModalContainer from '@app/components/modal-views/container';
import { useModal } from '@app/components/modal-views/context';
import { FULL_SCREEN_MODALS, useFullScreenModal } from '@app/components/modal-views/full-screen-modal-context';
import UpgradeToProModal from '@app/components/modal-views/modals/upgrade-to-pro-modal';
import WorkspacePreviewModal from '@app/components/modal-views/modals/workspace-preview-modal';
import { Dialog } from '@app/components/ui/dialog';
import { Transition } from '@app/components/ui/transition';
import { resetBuilderMenuState } from '@app/store/form-builder/actions';
import { useAppDispatch } from '@app/store/hooks';

import ConsentFullModalView from './full-screen-modals/consent-full-modal-view';
import CreateConsentFullModalView from './full-screen-modals/create-consent-full-modal-view';
import CropImageModalView from './modals/crop-image-modal-view';
import FormBuilderPreviewModal from './modals/form-builder-preview-modal';


function renderModalContent(view: FULL_SCREEN_MODALS, modalProps: any) {
    switch (view) {
        case 'LOGIN_VIEW':
            return <LoginView {...modalProps} />; // Done
        case 'FORM_BUILDER_PREVIEW':
            return <FormBuilderPreviewModal {...modalProps} />;
        case 'CROP_IMAGE':
            return <CropImageModalView {...modalProps} />;
        case 'UPGRADE_TO_PRO':
            return <UpgradeToProModal {...modalProps} />;
        case 'WORKSPACE_PREVIEW':
            return <WorkspacePreviewModal />;
        case 'CREATE_CONSENT_FULL_MODAL_VIEW':
            return <CreateConsentFullModalView {...modalProps} />;
        case 'CONSENT_FULL_MODAL_VIEW':
            return <ConsentFullModalView {...modalProps} />;

        default:
            return <></>;
    }
}

export default function FullScreenModalContainer() {
    const router = useRouter();
    const { isOpen, closeModal, modalProps, view } = useFullScreenModal();
    const { isOpen: isHalfScreenOpen } = useModal();
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
    }, [closeModal, router.events]);

    return (
        <>
            <Transition appear show={isOpen} as={Fragment}>
                <Dialog as="div"
                        className="fixed inset-0 z-[2500] h-full w-full overflow-y-auto overflow-x-hidden  text-center"
                        onClose={closeModalHandler}>
                    <Transition.Child as={Fragment} enter="ease-out duration-300" enterFrom="opacity-0"
                                      enterTo="opacity-100" leave="ease-in duration-200" leaveFrom="opacity-100"
                                      leaveTo="opacity-0">
                        <Dialog.Overlay
                            className={`fixed inset-0 z-40  ${view === 'UPGRADE_TO_PRO' || view === 'FORM_BUILDER_PREVIEW' ? '!bg-white' : 'bg-gray-700 bg-opacity-60'}   cursor-pointer`} />
                    </Transition.Child>

                    {/* This element is need to fix FocusTap headless-ui warning issue */}
                    <div className="sr-only">
                        <Button size="small" onClick={closeModalHandler} className="opacity-50 hover:opacity-80 ">
                            <Close className="h-auto w-[13px]" />
                        </Button>
                    </div>

                    <Transition.Child as={Fragment} enter="ease-out duration-300" enterFrom="opacity-0 scale-105"
                                      enterTo="opacity-100 scale-100" leave="ease-in duration-200"
                                      leaveFrom="opacity-100 scale-100" leaveTo="opacity-0 scale-105">
                        <div
                            data-testid="modal-view"
                            className={`relative min-h-screen flex flex-col items-center content-center !w-full  z-50  ${view === 'UPGRADE_TO_PRO' || view === 'FORM_BUILDER_PREVIEW' ? '!bg-white' : ''} text-left align-middle md:w-fit`}
                        >
                            {
                                //@ts-ignore
                                view && renderModalContent(view, modalProps)
                            }
                        </div>
                    </Transition.Child>
                    <ModalContainer />
                </Dialog>
            </Transition>
        </>
    );
}