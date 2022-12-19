import { Fragment, useEffect } from 'react';

import dynamic from 'next/dynamic';
import { useRouter } from 'next/router';

import { Close } from '@app/components/icons/close';
import Button from '@app/components/ui/button';
import { Dialog } from '@app/components/ui/dialog';
import { Transition } from '@app/components/ui/transition';

import LogoutView from '../logout/logout-view';
import { MODAL_VIEW, useModal } from './context';

// dynamic imports
const LoginView = dynamic(() => import('@app/components/login/login-view'));
const ImportFormsView = dynamic(() => import('@app/components/importforms'));

function renderModalContent(view: MODAL_VIEW | string) {
    switch (view) {
        case 'LOGIN_VIEW':
            return <LoginView />;
        case 'IMPORT_FORMS_VIEW':
            return <ImportFormsView />;
        case 'LOGOUT_VIEW':
            return <LogoutView />;
        default:
            return null;
    }
}

export default function ModalContainer() {
    const router = useRouter();
    const { view, isOpen, closeModal } = useModal();

    useEffect(() => {
        // close search modal when route change
        router.events.on('routeChangeStart', closeModal);
        return () => {
            router.events.off('routeChangeStart', closeModal);
        };
    }, []);

    return (
        <Transition appear show={isOpen} as={Fragment}>
            <Dialog as="div" className="fixed inset-0 z-50 h-full w-full overflow-y-auto overflow-x-hidden p-4 text-center sm:p-6 lg:p-8 xl:p-10 3xl:p-12" onClose={closeModal}>
                <Transition.Child as={Fragment} enter="ease-out duration-300" enterFrom="opacity-0" enterTo="opacity-100" leave="ease-in duration-200" leaveFrom="opacity-100" leaveTo="opacity-0">
                    <Dialog.Overlay className="fixed inset-0 z-40 cursor-pointer bg-gray-700 bg-opacity-60 backdrop-blur" />
                </Transition.Child>

                {/* This element is to trick the browser into centering the modal contents. */}
                {view && view !== 'SEARCH_VIEW' && (
                    <span className="inline-block h-full align-middle" aria-hidden="true">
                        &#8203;
                    </span>
                )}

                {/* This element is need to fix FocusTap headless-ui warning issue */}
                <div className="sr-only">
                    <Button size="small" color="gray" shape="circle" onClick={closeModal} className="opacity-50 hover:opacity-80 ">
                        <Close className="h-auto w-[13px]" />
                    </Button>
                </div>

                <Transition.Child as={Fragment} enter="ease-out duration-300" enterFrom="opacity-0 scale-105" enterTo="opacity-100 scale-100" leave="ease-in duration-200" leaveFrom="opacity-100 scale-100" leaveTo="opacity-0 scale-105">
                    <div className="relative z-50 inline-block w-full text-left align-middle xs:w-auto">{view && renderModalContent(view)}</div>
                </Transition.Child>
            </Dialog>
        </Transition>
    );
}
