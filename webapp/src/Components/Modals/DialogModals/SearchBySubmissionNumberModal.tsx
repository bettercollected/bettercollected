import SearchBySubmissionNumber from '@Components/RespondersPortal/SearchBySubmissionNumber';

import { Close } from '@app/components/icons/close';
import { useModal } from '@app/components/modal-views/context';

export default function SearchBySubmissionNumberModal() {
    const { closeModal } = useModal();

    return (
        <div className="w-full flex justify-center">
            <div className=" relative max-w-[367px]">
                <div className="absolute top-5 right-5" onClick={closeModal}>
                    <Close />
                </div>
                <SearchBySubmissionNumber />
            </div>
        </div>
    );
}
