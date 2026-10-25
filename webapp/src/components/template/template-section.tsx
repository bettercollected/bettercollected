import { useTranslation } from 'react-i18next';

import Empty from '@Components/icons/empty';

import { IFormTemplateDto } from '@app/models/dtos/template';
import { useAppSelector } from '@app/store/hooks';

import { selectAuth } from '@app/store/auth/slice';
import TemplateCard from './template-card';

/**
 * Which list this section shows. The styling follows this, never the
 * (translated) title: "predefined" is the ready-made gallery on a white band
 * without per-card menus; "workspace" holds the workspace's own templates.
 */
export type TemplateSectionVariant = 'predefined' | 'workspace';

interface ITemplateSectionProps {
    templates?: Array<IFormTemplateDto>;
    title?: string;
    variant?: TemplateSectionVariant;
    className?: string;
}

const TemplateSection = ({ templates, title = '', variant = 'workspace', className = '' }: ITemplateSectionProps) => {
    const auth = useAppSelector(selectAuth);
    const { t } = useTranslation();
    const isPredefinedTemplate = variant === 'predefined';
    return (
        <section data-testid="template-section" data-variant={variant} className={`flex w-full flex-col gap-6 p-10 px-4 md:px-10 ${isPredefinedTemplate ? 'bg-white' : ''} ${className}`}>
            {templates && templates.length > 0 && (
                <div className="flex justify-between">
                    <h1 className={'text-black-800 text-xl font-semibold'}>{title}</h1>
                </div>
            )}
            {/* Fixed-width columns that wrap as the page narrows: every card
                shows in full, rows grow with the list and nothing scrolls
                sideways. One column on a phone, centred. */}
            <div data-testid="template-grid" className="grid w-full grid-cols-[repeat(auto-fill,minmax(0,281px))] justify-center gap-6 md:justify-start">
                {templates && templates?.map((template: IFormTemplateDto, index: number) => <TemplateCard key={template?.id ?? index} template={template} isPredefinedTemplate={isPredefinedTemplate} />)}
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
        </section>
    );
};

export default TemplateSection;
