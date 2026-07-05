'use client';

import FullScreenModalContainer from '@app/components/modal-views/full-screen-modal-container';

import ModalContainer from '@app/components/modal-views/container';
import { useModal } from '@app/components/modal-views/context';
import { useFullScreenModal } from '@app/components/modal-views/full-screen-modal-context';
import { usePathname } from 'next/navigation';
import { useEffect } from 'react';
import { useBottomSheetModal } from '../contexts/bottom-sheet-modal-context';
import BottomSheetModalContainer from './bottom-sheet-modal-container';

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
