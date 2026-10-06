import SearchBySubmissionNumber from '@Components/responder-portal/search-by-submission-number';

import ModalCloseButton from '@app/components/modal-views/modal-close-button';
import { useModal } from '@app/components/modal-views/context';

export default function SearchBySubmissionNumberModal() {
    const { closeModal } = useModal();

    return (
        <div className="w-full flex justify-center">
            <div className=" relative max-w-[367px]">
                <ModalCloseButton onClick={closeModal} className="absolute right-4 top-4 h-8 w-8" iconClassName="h-6 w-6" />
                <SearchBySubmissionNumber />
            </div>
        </div>
    );
}
