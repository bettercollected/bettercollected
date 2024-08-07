import React, { useState } from 'react';

import { useTranslation } from 'next-i18next';
import { useRouter } from 'next/router';

import Divider from '@Components/Common/DataDisplay/Divider';
import AppTextField from '@Components/Common/Input/AppTextField';
import AppButton from '@Components/Common/Input/Button/AppButton';
import { ButtonSize } from '@Components/Common/Input/Button/AppButtonProps';

import { Close } from '@app/Components/icons/close';
import { useModal } from '@app/Components/modal-views/context';
import environments from '@app/configs/environments';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { useAppSelector } from '@app/store/hooks';


const ImportTemplateModalView = () => {
    const { closeModal } = useModal();
    const { t } = useTranslation();
    const router = useRouter();
    const workspace: WorkspaceDto = useAppSelector((state) => state.workspace);
    const [value, setValue] = useState('');

    const regexPattern = new RegExp(`^${environments.HTTP_SCHEME}${environments.ADMIN_DOMAIN}/templates/[0-9a-fA-F]{24}$`);

    const handlePreview = () => {
        if (regexPattern.test(value)) {
            const templateIdList = value.split('/');
            const templateId = templateIdList[templateIdList.length - 1];
            router.push(`/${workspace.workspaceName}/templates/${templateId}`);
        }
    };
    return (
        <div className=" bg-white w-[466px] rounded-[8px]">
            <div className={'flex justify-between px-4 py-[18px]'}>
                <h1 className={'text-sm font-normal text-black-800'}>Import Template</h1>
                <div className={'absolute top-3 right-5 cursor-pointer hover:bg-black-200 hover:rounded-sm p-1'}>
                    <Close
                        onClick={() => {
                            closeModal();
                        }}
                    />
                </div>
            </div>
            <Divider />
            <div className={'p-10 pt-6 flex flex-col gap-2'}>
                <h4 className="text-base font-medium text-black-800">Template Link</h4>
                <AppTextField value={value} onChange={(e: any) => setValue(e.target.value)} placeholder={'Enter or paste template link'} />
                <AppButton onClick={handlePreview} disabled={!regexPattern.test(value)} size={ButtonSize.Medium} className={'mt-4'}>
                    Preview Template
                </AppButton>
            </div>
        </div>
    );
};

export default ImportTemplateModalView;