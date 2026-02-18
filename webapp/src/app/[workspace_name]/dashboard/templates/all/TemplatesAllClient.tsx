'use client';

import React from 'react';
import { useTranslation } from 'react-i18next';
import { useRouter } from 'next/navigation';
import TemplateSection from '@Components/Template/TemplateSection';
import { ChevronForward } from '@app/Components/icons/chevron-forward';
import SidebarLayout from '@app/Components/sidebar/sidebar-layout';

export default function TemplatesAllClient({ predefined_templates }: { predefined_templates: any[] }) {
    const { t } = useTranslation();
    const router = useRouter();

    const handleClickBack = () => {
        router.back();
    };

    return (
        <SidebarLayout boxClassName="h-full bg-white !px-0">
            <div className="flex w-full cursor-pointer items-center gap-1 px-2 pt-2 md:px-5" onClick={handleClickBack}>
                <ChevronForward className="h-6 w-6 rotate-180 p-[2px]" />
                <p className="text-black-700 text-sm font-normal">{t('BUTTON.BACK')}</p>
            </div>
            <div className="mt-4 flex flex-col px-2 md:px-12">
                <h1 className="text-black-800 text-xl font-semibold">{t('TEMPLATE.ALL_TEMPLATES')}</h1>
                <TemplateSection templates={predefined_templates} className="md:pr-[80px] md:pl-[130px]" />
            </div>
        </SidebarLayout>
    );
}
