import { Fragment, useCallback } from 'react';

import { Button } from '@app/shadcn/components/ui/button';

import { Close } from '@app/components/icons/close';
import ModalContainer from '@app/components/modal-views/container';
import { FULL_SCREEN_MODALS, useFullScreenModal } from '@app/components/modal-views/full-screen-modal-context';
import UpgradeToProModal from '@app/components/modal-views/modals/upgrade-to-pro-modal';
import { Dialog } from '@app/components/ui/dialog';
import { Transition } from '@app/components/ui/transition';

import { PreviewFullModalView } from './full-screen-modals/v2preview-modal';
import ViewResponseFullModalView from './full-screen-modals/view-response-full-modal-view';

function renderModalContent(view: FULL_SCREEN_MODALS, modalProps: any) {
    switch (view) {
        case 'UPGRADE_TO_PRO':
            return <UpgradeToProModal {...modalProps} />;
        case 'VIEW_RESPONSE':
            return <ViewResponseFullModalView {...modalProps} />;
        case 'PREVIEW_MODAL':
            return <PreviewFullModalView {...modalProps} />;
        default:
            return <></>;
    }
}

export default function FullScreenModalContainer() {
    const { isOpen, closeModal, modalProps, view } = useFullScreenModal();

    const closeModalHandler = useCallback(() => {
        if (!modalProps?.nonClosable) closeModal();
    }, [closeModal, modalProps]);

    return (
        <>
            <Transition appear show={isOpen} as={Fragment}>
                <Dialog as="div" className="fixed inset-0 z-[2500] h-full w-full overflow-y-auto overflow-x-hidden  text-center" onClose={closeModalHandler}>
                    <Transition.Child as={Fragment} enter="ease-out duration-300" enterFrom="opacity-0" enterTo="opacity-100" leave="ease-in duration-200" leaveFrom="opacity-100" leaveTo="opacity-0">
                        <Dialog.Overlay className={`fixed inset-0 z-40  ${view === 'UPGRADE_TO_PRO' ? '!bg-white' : 'bg-gray-700 bg-opacity-60'}   cursor-pointer`} />
                    </Transition.Child>

                    {/* This element is need to fix FocusTap headless-ui warning issue */}
                    <div className="sr-only">
                        <Button variant="ghost" size="sm" onClick={closeModalHandler} className="opacity-50 hover:opacity-80 ">
                            <Close className="h-auto w-[13px]" />
                        </Button>
                    </div>

                    <Transition.Child as={Fragment} enter="ease-out duration-300" enterFrom="opacity-0 scale-105" enterTo="opacity-100 scale-100" leave="ease-in duration-200" leaveFrom="opacity-100 scale-100" leaveTo="opacity-0 scale-105">
                        <div
                            data-testid="modal-view"
                            className={`relative z-50 flex min-h-screen !w-full flex-col content-center  items-center  ${view === 'UPGRADE_TO_PRO' ? '!bg-white' : ''} text-left align-middle md:w-fit`}
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
