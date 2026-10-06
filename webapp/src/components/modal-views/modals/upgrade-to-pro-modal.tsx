
import ModalCloseButton from '@app/components/modal-views/modal-close-button';
import { useFullScreenModal } from '@app/components/modal-views/full-screen-modal-context';
import UpgradeToProContainer from '@app/containers/upgrade-to-pro';

export default function UpgradeToProModal({ callback }: { callback?: () => void }) {
    const { closeModal } = useFullScreenModal();

    return (
        <div className="h-full overflow-auto !bg-white pt-16 ">
            <ModalCloseButton onClick={closeModal} className="absolute right-5 top-5 h-12 w-12 lg:right-10 lg:top-10" iconClassName="h-10 w-10" />
            <UpgradeToProContainer callback={callback} />
        </div>
    );
}
