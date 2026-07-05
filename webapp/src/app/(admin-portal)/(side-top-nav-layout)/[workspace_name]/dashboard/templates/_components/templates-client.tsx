'use client';

import TemplateSection from '@Components/template/template-section';
import { selectAuth } from '@app/store/auth/slice';
import { useAppSelector } from '@app/store/hooks';
import { useGetTemplatesQuery } from '@app/store/template/api';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { LayoutTemplate } from 'lucide-react';
import { useTranslation } from 'react-i18next';

export default function TemplatesClient({ predefined_templates }: { predefined_templates: any[] }) {
    const { t } = useTranslation();
    const workspace = useAppSelector(selectWorkspace);
    const auth = useAppSelector(selectAuth);

    const isAdmin = auth?.roles?.includes('ADMIN');
    const predefined = isAdmin && Array.isArray(predefined_templates) ? [...predefined_templates] : [];

    const { data: v2Forms, isLoading } = useGetTemplatesQuery(
        { workspace_id: workspace?.id, v2: true },
        { skip: !workspace?.id }
    );
    const v2 = isAdmin && Array.isArray(v2Forms) ? v2Forms : [];

    const isEmpty = predefined.length === 0 && v2.length === 0;

    return (
        <>
            {predefined.length > 0 && (
                <TemplateSection title={t('TEMPLATE.DEFAULT')} templates={predefined} className="h-[400px]" />
            )}
            {v2.length > 0 && (
                <TemplateSection title={t('TEMPLATE.YOUR_WORKSPACE') + ' v2'} templates={v2} />
            )}
            {isEmpty && !isLoading && (
                <div className="flex min-h-[320px] w-full flex-col items-center justify-center gap-3 text-center">
                    <LayoutTemplate className="text-black-500 h-10 w-10" strokeWidth={1.5} />
                    <div className="h5-new text-black-800">No templates yet</div>
                    <p className="body4 text-black-600 max-w-[360px]">
                        Ready-made form templates will appear here. In the meantime, start from scratch or import an
                        existing form.
                    </p>
                </div>
            )}
        </>
    );
}
