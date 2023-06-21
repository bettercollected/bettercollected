import AddFieldGrid from '@Components/CreateForm/AddFieldGrid';

import { useFullScreenModal } from '@app/components/modal-views/full-screen-modal-context';

export default function AddFormFieldModal() {
    const { closeModal } = useFullScreenModal();

    return (
        <div
            className="w-full flex-1 !h-full flex flex-col justify-end"
            onClick={(event) => {
                if (event.target === event.currentTarget) {
                    closeModal();
                }
            }}
        >
            <div className="lg:ml-[289px] p-5 lg:p-10">
                <AddFieldGrid closeModal={closeModal} />;
            </div>
        </div>
    );
}
