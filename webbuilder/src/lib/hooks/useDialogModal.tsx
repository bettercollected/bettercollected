'use client';

import React, { useEffect } from 'react';

import { usePathname } from 'next/navigation';

import { atom, useAtom } from 'jotai';

import { Dialog, DialogContent } from '@app/shadcn/components/ui/dialog';
import AddFormTitleModal from '@app/views/molecules/Dialogs/AddFormTitleModal';
import FormPublishedModal from '@app/views/molecules/Dialogs/FormPublishedModal';
import UnsplashImagePicker from '@app/views/molecules/UnsplashImagePicker';

export type DIALOG_MODALS =
    | 'ADD_FORM_TITLE'
    | 'UNSPLASH_IMAGE_PICKER'
    | 'FORM_PUBLISHED'
    | '';

export interface ModalState {
    isOpen: boolean;
    view?: DIALOG_MODALS | '';
    props?: any;
}

const dialogModalAtom = atom<ModalState>({ isOpen: false });

export const useDialogModal = () => {
    const [modalState, setModalState] = useAtom(dialogModalAtom);

    const closeDialogModal = () => {
        setModalState({ isOpen: false, view: undefined, props: undefined });
    };

    const openDialogModal = (view: DIALOG_MODALS, props?: any) => {
        setModalState({ isOpen: true, view: view, props: props });
    };

    return {
        isOpen: modalState.isOpen,
        view: modalState.view,
        props: modalState.props,
        openDialogModal,
        closeDialogModal
    };
};

const getModalToRender = (view?: DIALOG_MODALS, props?: any) => {
    switch (view) {
        case 'ADD_FORM_TITLE':
            return <AddFormTitleModal />;
        case 'UNSPLASH_IMAGE_PICKER':
            return <UnsplashImagePicker {...props} />;
        case 'FORM_PUBLISHED':
            return <FormPublishedModal {...props} />;
        default:
            return <></>;
    }
};

export function DialogModalContainer() {
    const { isOpen, view, closeDialogModal, props } = useDialogModal();

    const pathname = usePathname();
    useEffect(() => {
        return () => {
            closeDialogModal();
        };
    }, [pathname]);

    return (
        <Dialog
            open={isOpen}
            onOpenChange={() => {
                closeDialogModal();
            }}
        >
            <DialogContent className="!bg-white !p-0">
                <div className="">{getModalToRender(view, props)}</div>
            </DialogContent>
        </Dialog>
    );
}

export function DialogModalTrigger({
    view,
    children,
    ...props
}: {
    view: DIALOG_MODALS;
    children: React.ReactNode;
    [key: string]: any;
}) {
    const { openDialogModal } = useDialogModal();
    return (
        <div
            onClick={(event) => {
                event.preventDefault();
                openDialogModal(view, props);
            }}
            className="h-full w-full"
        >
            {children}
        </div>
    );
}