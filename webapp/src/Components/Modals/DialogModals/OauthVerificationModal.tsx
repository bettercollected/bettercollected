import React, { useEffect } from 'react';

import { useRouter } from 'next/router';

import ImportErrorView from '@app/components/form-integrations/import-error-view';
import { useModal } from '@app/components/modal-views/context';

export default function OauthVerificationModal({ provider = 'google' }: { provider?: string }) {
    const { closeModal } = useModal();

    const router = useRouter();
    useEffect(() => {
        const blockCloseOnEscape = (event: KeyboardEvent) => {
            console.log();
            if (event.key == 'Escape' || event.key == 'Enter') {
                event.stopPropagation();
                event.preventDefault();
            }
        };
        const closeModalHandler = () => {
            closeModal();
        };
        document.addEventListener('keydown', blockCloseOnEscape);
        // close search modal when route change
        router.events.on('routeChangeStart', closeModalHandler);
        return () => {
            router.events.off('routeChangeStart', closeModalHandler);

            document.removeEventListener('keydown', blockCloseOnEscape);
        };
    }, []);

    return <ImportErrorView provider={provider} />;
}
