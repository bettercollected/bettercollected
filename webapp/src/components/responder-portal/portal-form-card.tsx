import { DotIcon } from '@Components/icons/dot-icon';

import { PortalAudience, usePortalText } from '@app/lib/hooks/use-respondent-language';
import { StandardFormDto } from '@app/models/dtos/form';
import { getFormFields } from '@app/utils/form-builder-block-utils';

interface IPortalFormCardProps {
    form: StandardFormDto;
    showPinned?: boolean;
    audience?: PortalAudience;
}

/**
 * A form on the responder portal. Responders don't care which platform built
 * the form or that a public form is "Public" — they care what it's for and
 * how big it is. Its own words are in the respondent's language (and marked
 * so); the form's title and purpose stay as the organisation wrote them.
 * The title is a heading (h3) under the list's h2, so screen-reader users can
 * jump from form to form.
 */
export default function PortalFormCard({ form, showPinned = true, audience = 'respondent' }: IPortalFormCardProps) {
    const { t, language } = usePortalText(audience);
    const questionCount = Array.isArray(form?.fields) ? getFormFields(form).length : 0;
    const pinned = showPinned && !!form?.settings?.pinned;

    return (
        <div className="hover:border-brand-500 flex h-full cursor-pointer flex-col items-start justify-between rounded border border-black-300 bg-white transition">
            <div className="flex w-full min-w-0 flex-col gap-2 rounded px-5 py-4">
                {form?.title ? (
                    <h3 className="h4-new">{form.title}</h3>
                ) : (
                    <h3 className="h4-new" lang={language}>
                        {t('PORTAL.UNTITLED_FORM')}
                    </h3>
                )}
                {form?.settings?.purpose && <p className="text-black-600 line-clamp-2 text-sm">{form.settings.purpose}</p>}
                {(questionCount > 0 || pinned) && (
                    <div className="text-black-600 flex max-w-full flex-wrap items-center gap-2 text-sm" lang={language}>
                        {questionCount > 0 && <span>{t('PORTAL.QUESTIONS', { count: questionCount })}</span>}
                        {questionCount > 0 && pinned && <DotIcon />}
                        {pinned && <span className="text-sm font-medium text-brand-olive">{t('PORTAL.PINNED')}</span>}
                    </div>
                )}
            </div>
        </div>
    );
}
