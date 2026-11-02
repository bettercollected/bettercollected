'use client';

import React from 'react';

import { ChevronRight } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import { sheetsReconnect } from '@app/constants/locales/sheets-reconnect';
import { Button } from '@app/shadcn/components/ui/button';
import { cn } from '@app/shadcn/util/lib';

import { Chip } from './summary';

const TONE: Record<Chip['kind'], string> = {
    on: 'border-green-300 bg-green-100 text-green-900',
    off: 'border-black-400 bg-black-100 text-black-800',
    'not-sent': 'border-amber-300 bg-amber-100 text-amber-900',
    'not-set-up': 'border-black-400 bg-black-100 text-black-800',
    unavailable: 'border-amber-300 bg-amber-100 text-amber-900',
    reconnect: 'border-amber-300 bg-amber-100 text-amber-900'
};

/** The status of a card as a word, never as colour alone. */
export function StatusChip({ chip }: { chip: Chip }) {
    const { t } = useTranslation();
    const { t: tb } = useTranslation('builder');
    const text = {
        on: () => tb('WEBHOOKS.LIST.ON'),
        off: () => tb('WEBHOOKS.LIST.OFF'),
        'not-sent': () => t('STAFF.FORM_SETTINGS.CARD_NOT_SENT', { count: chip.count ?? 0 }),
        'not-set-up': () => t('STAFF.FORM_SETTINGS.CARD_NOT_SET_UP'),
        unavailable: () => t('STAFF.FORM_SETTINGS.CARD_UNAVAILABLE'),
        reconnect: () => t(sheetsReconnect.badge)
    }[chip.kind]();
    return (
        <span data-testid="automation-chip" data-kind={chip.kind} className={cn('inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-semibold', TONE[chip.kind])}>
            {text}
        </span>
    );
}

export interface AutomationCardProps {
    /** Used for the ids the buttons carry, so the section can return focus to the one that opened a sheet. */
    id: string;
    title: string;
    summary: string;
    icon: React.ReactNode;
    chip: Chip | null;
    /** The primary action: Manage, or Set up while nothing is set up. Left out when the member may not configure. */
    manage?: { setUp: boolean; onClick: () => void; opener: string };
    deliveries?: { onClick: () => void; opener: string };
}

/**
 * One automation, as a card: icon, name, one line about it, a status in words,
 * and its buttons. The buttons carry the card's name for screen readers.
 */
export default function AutomationCard({ id, title, summary, icon, chip, manage, deliveries }: AutomationCardProps) {
    const { t } = useTranslation();
    const titleId = `automation-${id}-title`;
    return (
        <li data-testid={`automation-card-${id}`} className="flex flex-col gap-4 rounded-lg border border-black-300 bg-white p-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex min-w-0 items-start gap-4">
                <div aria-hidden="true" className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-black-300 bg-black-100 text-black-800">
                    {icon}
                </div>
                <div className="flex min-w-0 flex-col gap-1">
                    <div className="flex flex-wrap items-center gap-2">
                        <h3 id={titleId} className="text-[15px] font-semibold text-black-900">
                            {title}
                        </h3>
                        {chip && <StatusChip chip={chip} />}
                    </div>
                    <p className="text-sm leading-relaxed break-words text-black-700">{summary}</p>
                </div>
            </div>
            {(deliveries || manage) && (
                <div className="flex shrink-0 flex-wrap items-center gap-2">
                    {deliveries && (
                        <Button type="button" variant="v2Button" size="sm" data-panel-opener={deliveries.opener} aria-label={t('STAFF.FORM_SETTINGS.CARD_DELIVERIES_NAMED', { name: title })} onClick={deliveries.onClick}>
                            {t('STAFF.FORM_SETTINGS.CARD_DELIVERIES')}
                        </Button>
                    )}
                    {manage && (
                        <Button
                            type="button"
                            variant={manage.setUp ? 'primary' : 'secondary'}
                            size="sm"
                            data-panel-opener={manage.opener}
                            aria-label={t(manage.setUp ? 'STAFF.FORM_SETTINGS.CARD_SET_UP_NAMED' : 'STAFF.FORM_SETTINGS.CARD_MANAGE_NAMED', { name: title })}
                            postFixIcon={manage.setUp ? undefined : <ChevronRight aria-hidden="true" size={16} />}
                            onClick={manage.onClick}
                        >
                            {t(manage.setUp ? 'STAFF.FORM_SETTINGS.CARD_SET_UP' : 'STAFF.FORM_SETTINGS.CARD_MANAGE')}
                        </Button>
                    )}
                </div>
            )}
        </li>
    );
}
