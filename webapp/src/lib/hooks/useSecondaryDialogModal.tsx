'use client';

import React, { useEffect } from 'react';

import { usePathname } from 'next/navigation';

import { atom, useAtom } from 'jotai';

import { Dialog, DialogContent } from '@app/shadcn/components/ui/dialog';
import { cn } from '@app/shadcn/util/lib';
import DeleteMediaModal from '@app/views/molecules/Dialogs/DeleteMediaModal';

export type DIALOG_MODALS = 'DELETE_MEDIA' | '';

export interface ModalState {
    isOpen: boolean;
    view?: DIALOG_MODALS | '';
    props?: any;
}

const dialogModalAtom = atom<ModalState>({ isOpen: false });

export const useSecondaryDialogModal = () => {
    const [modalState, setModalState] = useAtom(dialogModalAtom);

    const closeSecondaryDialogModal = () => {
        setModalState({ isOpen: false, view: undefined, props: undefined });
    };

    const openSecondaryDialogModal = (view: DIALOG_MODALS, props?: any) => {
        setModalState({ isOpen: true, view: view, props: props });
    };

    return {
        isOpen: modalState.isOpen,
        view: modalState.view,
        props: modalState.props,
        openSecondaryDialogModal,
        closeSecondaryDialogModal
    };
};

const GetModalToRender = (view?: DIALOG_MODALS, props?: any) => {
    switch (view) {
        case 'DELETE_MEDIA':
            return <DeleteMediaModal {...props} />;
    }
};

const getClassName = (view?: DIALOG_MODALS) => {
    switch (view) {
        case 'DELETE_MEDIA':
            return 'md:!w-[450px]';
    }
};

export function SecondaryDialogModalContainer() {
    const { isOpen, view, closeSecondaryDialogModal, props } = useSecondaryDialogModal();

    const pathname = usePathname();
    useEffect(() => {
        return () => {
            closeSecondaryDialogModal();
        };
    }, [pathname]);

    return (
        <Dialog
            open={isOpen}
            onOpenChange={() => {
                closeSecondaryDialogModal();
            }}
        >
            <DialogContent onClickCloseIcon={closeSecondaryDialogModal} className={cn('z-[100] !bg-white !p-0 md:!min-w-[300px]', getClassName(view))}>
                {GetModalToRender(view, props)}
            </DialogContent>
        </Dialog>
    );
}
