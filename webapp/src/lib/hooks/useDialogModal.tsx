'use client';

import React, { useEffect } from 'react';

import { usePathname } from 'next/navigation';

import { atom, useAtom } from 'jotai';

import ShareView from '@app/Components/ui/share-view';
import { Dialog, DialogContent } from '@app/shadcn/components/ui/dialog';
import { cn } from '@app/shadcn/util/lib';
import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import AddFormTitleModal from '@app/views/molecules/Dialogs/AddFormTitleModal';
import FormPublishedModal from '@app/views/molecules/Dialogs/FormPublishedModal';
import StartWithAi from '@app/views/molecules/Dialogs/StartWithAIModal';
import UnsplashImagePicker from '@app/views/molecules/UnsplashImagePicker';

export type DIALOG_MODALS = 'ADD_FORM_TITLE' | 'UNSPLASH_IMAGE_PICKER' | 'FORM_PUBLISHED' | 'SHARE_FORM_MODAL' | 'START_WITH_AI' | '';

export interface ModalState {
    isOpen: boolean;
    view?: DIALOG_MODALS | '';
    props?: any;
}

function unsplashDefaultImageValue(type: string) {
    switch (type) {
        case 'Black':
            return 'Minimal White';
        case 'Purple':
            return 'Minimal Purple';
        case 'Red':
            return 'Minimal Red';
        case 'Orange':
            return 'Minimal Orange';
        case 'Blue':
            return 'Minimal Blue';
        case 'Green':
            return 'Minimal Green';
        default:
            return 'Minimal';
    }
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

const GetModalToRender = (view?: DIALOG_MODALS, props?: any) => {
    const form = useAppSelector(selectForm);

    switch (view) {
        case 'ADD_FORM_TITLE':
            return <AddFormTitleModal />;
        case 'UNSPLASH_IMAGE_PICKER':
            return <UnsplashImagePicker initialPhotoSearchQuery={unsplashDefaultImageValue(form?.theme?.title || 'Minimal')} {...props} />;
        case 'FORM_PUBLISHED':
            return <FormPublishedModal {...props} />;
        case 'SHARE_FORM_MODAL':
            return <ShareView {...props} />;
        case 'START_WITH_AI':
            return <StartWithAi />;
        default:
            return <></>;
    }
};

const getClassName = (view?: DIALOG_MODALS) => {
    switch (view) {
        case 'FORM_PUBLISHED':
            return 'md:!min-w-[760px]';
        case 'SHARE_FORM_MODAL':
            return 'md:!min-w-fit';
        case 'UNSPLASH_IMAGE_PICKER':
            return 'md:min-w-[550px] md:max-w-[550px] md:max-h-screen md:h-[520px] !rounded-lg';
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
            <DialogContent onClickCloseIcon={closeDialogModal} className={cn('!bg-white !p-0', getClassName(view))}>
                {GetModalToRender(view, props)}
            </DialogContent>
        </Dialog>
    );
}

export function DialogModalTrigger({ view, children, ...props }: { view: DIALOG_MODALS; children: React.ReactNode; [key: string]: any }) {
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
