'use client';

import { useBottomSheetModal } from '@app/components/Modals/Contexts/BottomSheetModalContext';
import FullScreenModalContainer from '@app/components/modal-views/full-screen-modal-container';

import ModalContainer from '@app/components/modal-views/container';
import { useModal } from '@app/components/modal-views/context';
import { useFullScreenModal } from '@app/components/modal-views/full-screen-modal-context';
import { usePathname } from 'next/navigation';
import { useEffect } from 'react';
import BottomSheetModalContainer from './BottomSheetModalContainer';

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
