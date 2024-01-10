import { useEffect } from 'react';

import { useRouter } from 'next/router';

import WorkspaceSettingsModal from '@Components/Modals/BottomSheetModals/WorkspaceSettingsModal';
import { BOTTOM_SCREEN_MODALS, useBottomSheetModal } from '@Components/Modals/Contexts/BottomSheetModalContext';
import { Button } from '@mui/material';
import { AnimatePresence, motion } from 'framer-motion';

import { Close } from '@app/components/icons/close';
import ModalContainer from '@app/components/modal-views/container';
import { Dialog } from '@app/components/ui/dialog';

const renderModalContent = (view: BOTTOM_SCREEN_MODALS, modalProps: any) => {
    switch (view) {
        case 'WORKSPACE_SETTINGS':
            return <WorkspaceSettingsModal {...modalProps} />;
        default:
            return <></>;
    }
};

export default function BottomSheetModalContainer() {
    const router = useRouter();
    const { isOpen, closeBottomSheetModal, modalProps, view } = useBottomSheetModal();

    useEffect(() => {
        // close search modal when route change
        router.events.on('routeChangeStart', closeBottomSheetModal);
        return () => {
            router.events.off('routeChangeStart', closeBottomSheetModal);
        };
    }, [closeBottomSheetModal, router.events]);

    return (
        <>
            <Dialog as="div" className="fixed inset-0 z-[2500] h-full w-full overflow-y-auto overflow-x-hidden  text-center" open={isOpen} onClose={closeBottomSheetModal}>
                {/* This element is need to fix FocusTap headless-ui warning issue */}
                <AnimatePresence mode="wait">
                    {view && (
                        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ ease: 'easeOut', duration: 0.5 }} className="!w-screen">
                            <Dialog.Overlay className={`fixed inset-0  bg-gray-700 bg-opacity-20   cursor-pointer`} />
                        </motion.div>
                    )}
                </AnimatePresence>
                <div className="sr-only">
                    <Button size="small" onClick={closeBottomSheetModal} className="opacity-50 hover:opacity-80 ">
                        <Close className="h-auto w-[13px]" />
                    </Button>
                </div>
                <div data-testid="modal-view" className={`relative min-h-screen flex flex-col items-center content-center !w-full  z-50 text-left align-middle md:w-fit`}>
                    <AnimatePresence mode="wait">
                        {view && (
                            <motion.div initial={{ opacity: 0, y: '100%' }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: '100%' }} transition={{ ease: 'easeOut', duration: 0.5 }} className="!w-screen">
                                {renderModalContent(view, modalProps)}
                            </motion.div>
                        )}
                    </AnimatePresence>
                </div>
                <ModalContainer />
            </Dialog>
        </>
    );
}
