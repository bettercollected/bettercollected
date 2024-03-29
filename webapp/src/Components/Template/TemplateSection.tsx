import React from 'react';

import { useTranslation } from 'next-i18next';
import Link from 'next/link';

import Empty from '@Components/Common/Icons/Common/Empty';
import AppButton from '@Components/Common/Input/Button/AppButton';
import { ButtonVariant } from '@Components/Common/Input/Button/AppButtonProps';
import CreateTemplateButton from '@Components/Template/CreateTemplateButton';
import VisibilityOutlinedIcon from '@mui/icons-material/VisibilityOutlined';

import { useModal } from '@app/components/modal-views/context';
import { IFormTemplateDto } from '@app/models/dtos/template';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';

import TemplateCard from './TemplateCard';


interface ITemplateSectionProps {
    templates?: Array<IFormTemplateDto>;
    title?: string;
    className?: string;
}

const TemplateSection = ({ templates, title = '', className }: ITemplateSectionProps) => {
    const workspace = useAppSelector(selectWorkspace);
    const { openModal } = useModal();
    const { t } = useTranslation();
    let isPredefinedTemplate: boolean = false;
    if (title == 'Default' || title === 'Standaard' || !title) {
        isPredefinedTemplate = true;
    }
    return (
        <div className={`flex flex-col gap-6 p-10 px-4 md:px-10 w-full ${title == 'Default' && 'bg-white'} ${className}`}>
            {templates && templates.length > 0 && (
                <div className={`flex  md:flex-row justify-between ' ${title == 'Default' ? 'flex-row' : 'flex-col gap-2'}`}>
                    <h1 className={'text-xl font-semibold text-black-800'}>{title}</h1>
                    {title === '' ? (
                        <></>
                    ) : isPredefinedTemplate ? (
                        <Link href={`/${workspace.workspaceName}/dashboard/templates/all`}>
                            <div className={'flex flex-row gap-2 items-center text-blue-500 cursor-pointer'}>
                                <VisibilityOutlinedIcon />
                                <p className={'text-sm font-medium text-blue-500'}>{t('TEMPLATE.SHOW_ALL')}</p>
                            </div>
                        </Link>
                    ) : (
                        <div className={'flex flex-row gap-4'}>
                            <AppButton variant={ButtonVariant.Secondary} onClick={() => openModal('IMPORT_TEMPLATE_MODAL_VIEW')}>
                                {t('TEMPLATE.BUTTONS.IMPORT_TEMPLATE')}
                            </AppButton>
                            <CreateTemplateButton />
                        </div>
                    )}
                </div>
            )}
            <div className={`flex flex-row  w-full gap-6 ${title == 'Default' || title === 'Standaard' ? 'flex-nowrap overflow-auto' : 'flex-wrap justify-center md:justify-start'}`}>
                {templates && templates?.map((template: IFormTemplateDto, index: number) => <TemplateCard key={index} template={template} isPredefinedTemplate={isPredefinedTemplate} />)}
            </div>

            {!templates ||
                (templates.length == 0 && (
                    <div className="flex flex-col gap-2 w-full items-center">
                        <Empty />
                        <div className="mt-10 h4-new text-black-800">{t('TEMPLATE.NOT_FOUND.TITLE')}</div>
                        <div className="p2-new text-black-700">{t('TEMPLATE.NOT_FOUND.DESC')}</div>
                        <div className="flex gap-4 mt-10">
                            <div className={'flex flex-row gap-4'}>
                                <AppButton variant={ButtonVariant.Secondary} onClick={() => openModal('IMPORT_TEMPLATE_MODAL_VIEW')}>
                                    {t('TEMPLATE.BUTTONS.IMPORT_TEMPLATE')}
                                </AppButton>
                                <CreateTemplateButton />
                            </div>
                        </div>
                    </div>
                ))}
        </div>
    );
};

export default TemplateSection;