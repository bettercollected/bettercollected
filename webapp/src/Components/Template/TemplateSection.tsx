import React from 'react';

import { useTranslation } from 'next-i18next';
import Link from 'next/link';

import Empty from '@Components/Common/Icons/Common/Empty';
import { Eye } from 'lucide-react';

import { IFormTemplateDto } from '@app/models/dtos/template';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';

import TemplateCard from './TemplateCard';
import { selectAuth } from '@app/store/auth/slice';

interface ITemplateSectionProps {
    templates?: Array<IFormTemplateDto>;
    title?: string;
    showButtons?: boolean;
    className?: string;
}

const TemplateSection = ({ templates, title = '', className, showButtons = true }: ITemplateSectionProps) => {
    const auth = useAppSelector(selectAuth);
    const workspace = useAppSelector(selectWorkspace);
    const { t } = useTranslation();
    let isPredefinedTemplate: boolean = false;
    if (title == 'Default' || title === 'Standaard' || !title) {
        isPredefinedTemplate = true;
    }
    return (
        <div className={`flex w-full flex-col gap-6 p-10 px-4 md:px-10 ${title == 'Default' && 'bg-white'} ${className}`}>
            {templates && templates.length > 0 && (
                <div className={`'  flex justify-between md:flex-row ${title == 'Default' ? 'flex-row' : 'flex-col gap-2'}`}>
                    <h1 className={'text-black-800 text-xl font-semibold'}>{title}</h1>
                    {showButtons && (
                        <>
                            {title === '' ? (
                                <></>
                            ) : isPredefinedTemplate ? (
                                <Link href={`/${workspace.workspaceName}/dashboard/templates/all`} legacyBehavior>
                                    <div className={'flex cursor-pointer flex-row items-center gap-2 text-blue-500'}>
                                        <Eye className="w-5 h-5" />
                                        <p className={'text-sm font-medium text-blue-500'}>{t('TEMPLATE.SHOW_ALL')}</p>
                                    </div>
                                </Link>
                            ) : null}
                        </>
                    )}
                </div>
            )}
            <div className={`flex w-full flex-col  flex-wrap gap-6 md:flex-row ${title == 'Default' || title === 'Standard' ? ' overflow-x-auto' : ' justify-center md:justify-start'}`}>
                {templates && templates?.map((template: IFormTemplateDto, index: number) => <TemplateCard key={index} template={template} isPredefinedTemplate={isPredefinedTemplate} />)}
            </div>

            {!templates ||
                (templates.length == 0 && (
                    <div className="flex w-full flex-col items-center gap-2">
                        <Empty />
                        <div className="h4-new text-black-800 mt-10">{t('TEMPLATE.NOT_FOUND.TITLE')}</div>
                        {auth?.roles?.includes('ADMIN') && (
                            <>
                                <div className="p2-new text-black-700">{t('TEMPLATE.NOT_FOUND.DESC')}</div>
                            </>
                        )}
                    </div>
                ))}
        </div>
    );
};

export default TemplateSection;
