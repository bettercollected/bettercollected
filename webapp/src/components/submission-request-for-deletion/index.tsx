import React, { useRef } from 'react';

import { Close } from '@app/components/icons/close';
import { useModal } from '@app/components/modal-views/context';
import Button from '@app/components/ui/button';

export default function RequestForDeletionView(props: any) {
    const { closeModal } = useModal();
    const { handleRequestForDeletion } = props;

    const ref = useRef<HTMLDivElement>(null);

    const handleDelete = () => {
        if (handleRequestForDeletion) {
            handleRequestForDeletion(closeModal);
        }
    };

    return (
        <div ref={ref} className="relative m-auto w-full items-start justify-between rounded-lg bg-white">
            <div className="relative max-w-[465px] text-center flex flex-col items-center justify-between p-10">
                <svg aria-hidden="true" className="mx-auto mb-4 text-gray-400 w-14 h-14 dark:text-gray-200" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                </svg>
                <h3 className="mb-5 text-lg font-normal max-w-[352px] text-gray-500 dark:text-gray-400">Are you sure you want to request your response to be deleted?</h3>
                <div className="flex items-center justify-between">
                    <Button variant="solid" color="gray" size="medium" className="!bg-black-500 mr-2" onClick={closeModal}>
                        No, Cancel
                    </Button>
                    {/*<button*/}
                    {/*    data-modal-hide="popup-modal"*/}
                    {/*    type="button"*/}
                    {/*    onClick={closeModal}*/}
                    {/*    className="text-gray-500 bg-white hover:bg-gray-100 focus:ring-4 focus:outline-none focus:ring-gray-200 rounded-lg border border-gray-200 text-sm font-medium px-5 py-2.5 hover:text-gray-900 focus:z-10 dark:bg-gray-700 dark:text-gray-300 dark:border-gray-500 dark:hover:text-white dark:hover:bg-gray-600 dark:focus:ring-gray-600"*/}
                    {/*>*/}
                    {/*    No, cancel*/}
                    {/*</button>*/}

                    <Button data-testid="logout-button" variant="solid" size="medium" color="danger" onClick={handleDelete}>
                        Yes, I&apos;m sure
                    </Button>
                    {/*<button*/}
                    {/*    data-modal-hide="popup-modal"*/}
                    {/*    type="button"*/}
                    {/*    onClick={() => handleDelete()}*/}
                    {/*    className="text-white bg-red-600 hover:bg-red-800 focus:ring-4 focus:outline-none focus:ring-red-300 dark:focus:ring-red-800 font-medium rounded-lg text-sm inline-flex items-center px-5 py-2.5 text-center mr-2"*/}
                    {/*>*/}
                    {/*    Yes, I&apos;m sure*/}
                    {/*</button>*/}
                </div>
            </div>
            <Close onClick={() => closeModal()} className="cursor-pointer absolute top-3 right-3 h-auto w-3 text-gray-600 hover:text-black dark:text-white" />
        </div>
    );
}
