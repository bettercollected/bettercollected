import React, { useContext, useEffect, useState } from 'react';

import { useTranslation } from 'next-i18next';
import { useRouter } from 'next/router';

import Tooltip from '@Components/Common/DataDisplay/Tooltip';
import AppButton from '@Components/Common/Input/Button/AppButton';
import { ButtonSize, ButtonVariant } from '@Components/Common/Input/Button/AppButtonProps';
import useDrivePicker from '@fyelci/react-google-drive-picker';

import FormProviderContext from '@app/Contexts/FormProviderContext';
import { buttonConstant } from '@app/constants/locales/button';
import { toolTipConstant } from '@app/constants/locales/tooltip';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';

export default function ImportFormsButton({ size, className = '' }: { size?: ButtonSize; className?: string }) {
    const router = useRouter();
    const { t } = useTranslation();
    const formProviders = useContext(FormProviderContext);

    const workspace = useAppSelector(selectWorkspace);

    const [providers, setProviders] = useState<Record<string, boolean>>({
        google: false,
        typeform: false
    });

    const [openPicker] = useDrivePicker();

    const handleClick = () => {
        // router.push(`/${workspace?.workspaceName}/dashboard/forms/import`);
        openPicker({
            clientId: '132120488980-hdf9tjq86k4km9kad2et532si5khuri9.apps.googleusercontent.com',
            developerKey: 'AIzaSyA6OLL3bCqL2q3A5pl6CoPLq9LLO-p2-ok',
            viewId: 'FORMS',
            // token: 'ya29.a0AfB_byBmSGCAwYH-j19Ay2xd9pwghLNfB-qgrDzIdtZsjfgGRK9A1eG0LreT28QURwG8rMw7q06NYsqciBIzuzqXHzMOZrAUrrEOZ6hO3vZ1jgZFp3V0mCxXLUeG2cvXbp4mv-2lmgDITKWD-XvmRXKk91KukMrW5zpcbQaCgYKARISARMSFQHGX2MiKG-chxR44odTwCjOlPuUeQ0173',
            customScopes: ['https://www.googleapis.com/auth/drive.file'],
            callbackFunction: (data) => {
                console.log(data);
                if (data.action === 'cancel') {
                    router.push(router.asPath);
                }
            }
        });
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
