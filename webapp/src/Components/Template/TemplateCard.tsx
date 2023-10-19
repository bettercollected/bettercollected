import React from 'react';

import { useRouter } from 'next/router';

import { IFormTemplateDto } from '@app/models/dtos/template';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';

interface ITemplateCardProps {
    template: IFormTemplateDto;
    isPredefinedTemplate: boolean;
}

const TemplateCard = ({ template, isPredefinedTemplate }: ITemplateCardProps) => {
    const router = useRouter();
    const workspace = useAppSelector(selectWorkspace);
    const handleClickCard = () => {
        router.push(`/${workspace.workspaceName}/templates/${template.id}`);
    };

    return (
        <div className={'flex flex-col gap-1 cursor-pointer'} onClick={handleClickCard}>
            <div className={'h-40 w-[205px] bg-blue-500'}>
                <h1>sahdjhasjd</h1>
            </div>
            <h1 className={'text-sm font-semibold text-black-800'}>{template.title}</h1>
            {!isPredefinedTemplate && (
                <h1 className={'text-xs font-normal text-black-600'}>
                    Created: <span className={'text-black-800'}>{template?.importedFrom ? template.importedFrom : 'Default'}</span>
                </h1>
            )}
        </div>
    );
};

export default TemplateCard;
