import React, { useContext, useEffect, useState } from 'react';

import { useTranslation } from 'next-i18next';
import { useRouter } from 'next/router';

import Tooltip from '@Components/Common/DataDisplay/Tooltip';
import AppButton from '@Components/Common/Input/Button/AppButton';
import { ButtonSize, ButtonVariant } from '@Components/Common/Input/Button/AppButtonProps';
import useDrivePicker from '@fyelci/react-google-drive-picker';

import FormProviderContext from '@app/Contexts/FormProviderContext';
import { useModal } from '@app/components/modal-views/context';
import environments from '@app/configs/environments';
import { buttonConstant } from '@app/constants/locales/button';
import { toolTipConstant } from '@app/constants/locales/tooltip';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';

export default function ImportFormsButton({ size, className = '' }: { size?: ButtonSize; className?: string }) {
    const { t } = useTranslation();
    const formProviders = useContext(FormProviderContext);
    const { openModal } = useModal();
    const [openPicker] = useDrivePicker();

    const workspace = useAppSelector(selectWorkspace);
    const router = useRouter();
    const [providers, setProviders] = useState<Record<string, boolean>>({
        google: false,
        typeform: false
    });

    useEffect(() => {
        const { modal, ...other } = router.query;
        if (typeof modal === 'string' && modal === 'true') {
            router.push({ query: other }, undefined, { shallow: true }).then(() => {
                openModal('IMPORT_FORMS', { nonClosable: true });
            });
        }
    }, []);

    const handleClick = () => {
        if (environments.ENABLE_IMPORT_WITH_PICKER) {
            openModal('IMPORT_FORMS', { nonClosable: true });
        } else {
            router.push(`/${workspace.workspaceName}/dashboard/forms/import`);
        }
    };

    useEffect(() => {
        const providersRecord: Record<string, boolean> = {};
        formProviders.forEach((provider) => {
            // TODO: change this to provider.enabled in the value
            providersRecord[provider.providerName] = !!provider.providerName;
        });
        setProviders({ ...providers, ...providersRecord });
    }, [formProviders]);

    const importFormButton = (
        <span>
            <AppButton variant={ButtonVariant.Secondary} className={`${className} min-w-[160px]`} disabled={!providers.google && !providers.typeform} size={size} onClick={handleClick}>
                {t(buttonConstant.importForms)}
            </AppButton>
        </span>
    );

    if (!providers.google && !providers.typeform) {
        return <Tooltip title={t(toolTipConstant.formProviderHidden)}>{importFormButton}</Tooltip>;
    }

    return importFormButton;
}
