
import { Button } from '@app/shadcn/components/ui/button';
import CreateGroupModal from '@Components/modals/bottom-sheet-modals/create-group-modal';
import DeleteAccountModal from '@Components/modals/bottom-sheet-modals/delete-account-modal';
import TemplateSettingsModal from '@Components/modals/bottom-sheet-modals/template-settings-modal';
import WorkspaceSettingsModal from '@Components/modals/bottom-sheet-modals/workspace-settings-modal';
import { AnimatePresence, motion } from 'framer-motion';

import { Close } from '@app/components/icons/close';
import ModalContainer from '@app/components/modal-views/container';
import FormCreateSlugFullModalView from '@app/components/modal-views/full-screen-modals/create-form-slug-full-modal-view';
import SelectGroupFullModalView from '@app/components/modal-views/full-screen-modals/select-group-modal-view';
import ScheduleFormCloseDateModal from '@app/components/modal-views/modals/schedule-form-close-date-modal';
import { Dialog, DialogBackdrop } from '@app/components/ui/dialog';
import { BOTTOM_SCREEN_MODALS, useBottomSheetModal } from '../contexts/bottom-sheet-modal-context';

const renderModalContent = (view: BOTTOM_SCREEN_MODALS, modalProps: any) => {
    switch (view) {
        case 'WORKSPACE_SETTINGS':
            return <WorkspaceSettingsModal {...modalProps} />;
        case 'SELECT_FORM_CLOSE_DATE':
            return <ScheduleFormCloseDateModal {...modalProps} />;
        case 'TEMPLATE_SETTINGS_FULL_MODAL_VIEW':
            return <TemplateSettingsModal {...modalProps} />;
        case 'FORM_CREATE_SLUG_VIEW':
            return <FormCreateSlugFullModalView {...modalProps} />;
        case 'SELECT_GROUP_FULL_MODAL_VIEW':
            return <SelectGroupFullModalView {...modalProps} />;
        case 'CREATE_GROUP':
            return <CreateGroupModal {...modalProps} />;
        case 'DELETE_ACCOUNT':
            return <DeleteAccountModal />;
        default:
            return <></>;
    }
};

export default function BottomSheetModalContainer() {
    const { isOpen, closeBottomSheetModal, modalProps, view } = useBottomSheetModal();

    return (
        <>
            <Dialog as="div" className="fixed inset-0 z-[2500] h-full w-full overflow-y-auto overflow-x-hidden  text-center" open={isOpen} onClose={closeBottomSheetModal}>
                {/* This element is need to fix FocusTap headless-ui warning issue */}
                <AnimatePresence mode="wait">
                    {view && (
                        <motion.div
                            {...({
                                initial: { opacity: 0 },
                                animate: { opacity: 1 },
                                exit: { opacity: 0 },
                                transition: { ease: 'easeOut', duration: 0.5 },
                                className: '!w-screen'
                            } as any)}
                        >
                            <DialogBackdrop className={`fixed inset-0  cursor-pointer bg-gray-700  bg-opacity-60`} />
                        </motion.div>
                    )}
                </AnimatePresence>
                <div className="sr-only">
                    <Button variant="ghost" size="sm" onClick={closeBottomSheetModal} className="opacity-50 hover:opacity-80 ">
                        <Close className="h-auto w-[13px]" />
                    </Button>
                </div>
                <div data-testid="modal-view" className={`relative z-50 flex min-h-screen !w-full flex-col content-center  items-center text-left align-middle md:w-fit`}>
                    <AnimatePresence mode="wait">
                        {view && (
                            <motion.div
                                {...({
                                    initial: { opacity: 0, y: '100%' },
                                    animate: { opacity: 1, y: 0 },
                                    exit: { opacity: 0, y: '100%' },
                                    transition: { ease: 'easeOut', duration: 0.5 },
                                    className: '!w-screen'
                                } as any)}
                            >
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
