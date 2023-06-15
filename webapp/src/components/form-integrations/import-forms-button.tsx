import React, { useContext, useEffect, useState } from 'react';

import { useTranslation } from 'next-i18next';
import { useRouter } from 'next/router';

import Tooltip from '@Components/Common/DataDisplay/Tooltip';

import FormProviderContext from '@app/Contexts/FormProviderContext';
import { useModal } from '@app/components/modal-views/context';
import Button, { ButtonProps } from '@app/components/ui/button';
import { buttonConstant } from '@app/constants/locales/button';
import { toolTipConstant } from '@app/constants/locales/tooltip';

export default function ImportFormsButton({ size, className = '' }: ButtonProps) {
    const { openModal } = useModal();
    const router = useRouter();
    const { t } = useTranslation();
    const formProviders = useContext(FormProviderContext);

    const [providers, setProviders] = useState<Record<string, boolean>>({
        google: false,
        typeform: false
    });

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

    useEffect(() => {
        const providersRecord: Record<string, boolean> = {};
        formProviders.forEach((provider) => {
            // TODO: change this to provider.enabled in the value
            providersRecord[provider.providerName] = !!provider.providerName;
        });
        setProviders({ ...providers, ...providersRecord });
    }, [formProviders]);

    const importFormButton = (
        <Button variant="solid" className={`w-full sm:w-auto ${className}`} disabled={!providers.google && !providers.typeform} size={size} onClick={handleClick}>
            {t(buttonConstant.importForms)}
        </Button>
    );

    if (!providers.google && !providers.typeform) {
        return <Tooltip title={t(toolTipConstant.formProviderHidden)}>{importFormButton}</Tooltip>;
    }

    return importFormButton;
}
