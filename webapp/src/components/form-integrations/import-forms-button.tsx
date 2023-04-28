import React, { useEffect } from 'react';

import { useRouter } from 'next/router';

import { Tooltip } from '@mui/material';

import { useModal } from '@app/components/modal-views/context';
import Button, { ButtonProps } from '@app/components/ui/button';
import environments from '@app/configs/environments';

export default function ImportFormsButton({ size }: ButtonProps) {
    const { openModal } = useModal();
    const router = useRouter();

    const googleEnabled = environments.ENABLE_GOOGLE;
    const typeformEnabled = environments.ENABLE_TYPEFORM;

    const providers: Record<string, boolean> = {
        google: !!googleEnabled,
        typeform: !!typeformEnabled
    };

    const handleClick = () => {
        openModal('IMPORT_PROVIDER_FORMS_VIEW', { provider: null, providers });
    };

    useEffect(() => {
        const { modal, ...other } = router.query;
        if (modal) {
            router.push({ query: other }, undefined, { shallow: true }).then(() => {
                switch (modal) {
                    case 'google':
                        openModal('IMPORT_PROVIDER_FORMS_VIEW', { provider: 'google', providers });
                        break;
                    case 'typeform':
                        openModal('IMPORT_PROVIDER_FORMS_VIEW', { provider: 'typeform', providers });
                        break;
                    default:
                        break;
                }
            });
        }
    }, []);

    const importFormButton = (
        <Button variant="solid" className="w-full sm:w-auto" disabled={!googleEnabled && !typeformEnabled} size={size} onClick={handleClick}>
            Import Forms
        </Button>
    );

    if (!googleEnabled && !typeformEnabled) {
        return (
            <Tooltip arrow placement="bottom-end" title="Form Providers are disabled.">
                {importFormButton}
            </Tooltip>
        );
    }

    return importFormButton;
}
