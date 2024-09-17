'use client';
import dynamic from 'next/dynamic';

import { useBottomSheetModal } from '@Components/Modals/Contexts/BottomSheetModalContext';

import { useModal } from '@app/Components/modal-views/context';
import { useFullScreenModal } from '@app/Components/modal-views/full-screen-modal-context';
import { useEffect } from 'react';
import { usePathname } from 'next/navigation';

const ModalContainer = dynamic(() => import('@app/Components/modal-views/container'));
const FullScreenModalContainer = dynamic(() => import('@app/Components/modal-views/full-screen-modal-container'));
const BottomSheetModalContainer = dynamic(() => import('@app/Components/Modals/Containers/BottomSheetModalContainer'));

export default function BaseModalContainer() {
    const { isOpen, closeModal } = useModal();
    const { isOpen: isFullScreenModalOpen, closeModal: closeFullScreenModal } = useFullScreenModal();
    const { isOpen: isBottomSheetModalOpen, closeBottomSheetModal } = useBottomSheetModal();

    const pathname = usePathname();

    useEffect(() => {
        closeModal();
        closeFullScreenModal();
        closeBottomSheetModal();
    }, [pathname]);

    if (isFullScreenModalOpen) return <FullScreenModalContainer />;
    if (isBottomSheetModalOpen) return <BottomSheetModalContainer />;
    if (isOpen) return <ModalContainer />;

    return <></>;
}
