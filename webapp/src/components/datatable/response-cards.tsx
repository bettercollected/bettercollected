import Link from 'next/link';

import { useTranslation } from 'react-i18next';

import { StandardFormResponseDto } from '@app/models/dtos/form';
import { utcToLocalDateTimeIn } from '@app/utils/date-utils';

import AnonymousBadge from './anonymous-badge';

export interface ResponseCardPreview {
    key: string;
    title: string;
    text: string;
}

interface Props {
    responses: StandardFormResponseDto[];
    /** The address of a response's own page. */
    hrefFor: (response: StandardFormResponseDto) => string;
    /** The first answers of a response, to tell it from the next (already readable text). */
    previews: (response: StandardFormResponseDto) => ResponseCardPreview[];
}

/**
 * The responses list on a phone: one card per response instead of a table
 * that would leave 40 pixels for the answers. The responder (or the Anonymous
 * mark) is the card's link to the response's page, so the whole card opens it
 * and a screen reader hears one link per response, named by who answered; below
 * it the submitted time, the form version and the first answers.
 */
export default function ResponseCards({ responses, hrefFor, previews }: Props) {
    const { t, i18n } = useTranslation();
    return (
        <ul aria-label={t('RESPONSES_STAFF.RESPONSE_LIST')} className="flex flex-col gap-2">
            {responses.map((response) => {
                const rows = previews(response);
                const owner = response.dataOwnerIdentifier;
                return (
                    <li key={response.responseId} className="relative flex flex-col gap-2 rounded border border-black-300 bg-white p-3 focus-within:bg-black-100 hover:bg-black-100">
                        <Link
                            href={hrefFor(response)}
                            aria-label={owner ? t('RESPONSES_STAFF.OPEN_NAMED', { name: owner }) : t('RESPONSES_STAFF.OPEN_ANONYMOUS')}
                            className="flex w-fit max-w-full min-w-0 rounded after:absolute after:inset-0 after:content-[''] focus:outline-hidden focus-visible:ring-2 focus-visible:ring-brand-500"
                        >
                            {owner ? <span className="truncate text-sm font-medium text-black-900">{owner}</span> : <AnonymousBadge />}
                        </Link>
                        <p className="text-xs text-black-600">
                            {t('RESPONSES_STAFF.SUBMITTED_AT', { time: utcToLocalDateTimeIn(response.createdAt, i18n.language) })}
                            {typeof response.formVersion === 'number' && <span> · {t('RESPONSES_STAFF.VERSION_SHORT', { n: response.formVersion })}</span>}
                        </p>
                        {rows.length > 0 && (
                            <dl className="flex flex-col gap-1.5">
                                {rows.map((row) => (
                                    <div key={row.key} className="flex min-w-0 flex-col">
                                        <dt className="truncate text-xs text-black-600">{row.title}</dt>
                                        <dd className="line-clamp-2 text-sm [overflow-wrap:anywhere] text-black-800">{row.text}</dd>
                                    </div>
                                ))}
                            </dl>
                        )}
                    </li>
                );
            })}
        </ul>
    );
}
