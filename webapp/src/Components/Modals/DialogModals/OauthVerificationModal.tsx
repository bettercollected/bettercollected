import React, { useEffect } from 'react';

import ImportErrorView from '@app/components/form-integrations/import-error-view';

export default function OauthVerificationModal({ provider = 'google' }: { provider?: string }) {
    useEffect(() => {
        const blockCloseOnEscape = (event: KeyboardEvent) => {
            console.log();
            if (event.key == 'Escape' || event.key == 'Enter') {
                event.stopPropagation();
                event.preventDefault();
            }
        };
        document.addEventListener('keydown', blockCloseOnEscape);
        return () => {
            document.removeEventListener('keydown', blockCloseOnEscape);
        };
    }, []);

    return <ImportErrorView provider={provider} />;
}
