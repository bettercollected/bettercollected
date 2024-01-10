import dynamic from 'next/dynamic';

import { useBottomSheetModal } from '@Components/Modals/Contexts/BottomSheetModalContext';

import { useModal } from '@app/components/modal-views/context';
import { useFullScreenModal } from '@app/components/modal-views/full-screen-modal-context';

const ModalContainer = dynamic(() => import('@app/components/modal-views/container'));
const FullScreenModalContainer = dynamic(() => import('@app/components/modal-views/full-screen-modal-container'));
const BottomSheetModalContainer = dynamic(() => import('@app/Components/Modals/Containers/BottomSheetModalContainer'));
export default function BaseModalContainer() {
    const { isOpen } = useModal();
    const { isOpen: isFullScreenModalOpen } = useFullScreenModal();
    const { isOpen: isBottomSheetModalOpen } = useBottomSheetModal();

    if (isFullScreenModalOpen) return <FullScreenModalContainer />;
    if (isBottomSheetModalOpen) return <BottomSheetModalContainer />;
    if (isOpen) return <ModalContainer />;

    return <></>;
}
