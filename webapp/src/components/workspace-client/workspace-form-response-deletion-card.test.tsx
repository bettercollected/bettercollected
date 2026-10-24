import React from 'react';
import { render, screen } from '@testing-library/react';
import i18n from 'i18next';
import { describe, expect, it } from 'vitest';

import I18nProvider from '@app/shared/hocs/i18n-provider';
import { StandardFormResponseDto } from '@app/models/dtos/form';

import WorkspaceFormResponseDeletionCard, { deletionStatusLabel } from './workspace-form-response-deletion-card';

const request = (status: string, declineReason?: string): StandardFormResponseDto =>
    ({
        responseId: 'r1',
        provider: 'google',
        formTitle: 'Imported form',
        createdAt: '2026-01-02T03:04:05Z',
        updatedAt: '2026-01-03T03:04:05Z',
        dataOwnerIdentifier: 'someone@example.com',
        status,
        declineReason
    }) as StandardFormResponseDto;

const renderCard = (response: StandardFormResponseDto) =>
    render(
        <I18nProvider>
            <WorkspaceFormResponseDeletionCard response={response} deletionRequests workspaceName="acme" />
        </I18nProvider>
    );

describe('deletion request status on the respondent card', () => {
    it('never tells the respondent a declined request was deleted', () => {
        renderCard(request('declined', 'legal_obligation'));
        expect(screen.getByText('Not deleted: the organisation must keep it by law')).toBeDefined();
        expect(screen.queryByText(/^Deleted/)).toBeNull();
    });

    it('says deleted only for a completed request', () => {
        renderCard(request('success'));
        expect(screen.getByText(/^Deleted \(/)).toBeDefined();
    });

    it('shows a pending request as requested', () => {
        renderCard(request('pending'));
        expect(screen.getByText('Deletion requested')).toBeDefined();
    });

    it('falls back to the generic reason and never to "Deleted" for unknown values', () => {
        renderCard(request('declined', 'something-new'));
        expect(screen.getByText('Not deleted: the organisation declined the request')).toBeDefined();
        renderCard(request('archived'));
        expect(screen.queryByText(/^Deleted/)).toBeNull();
    });

    it('has the Dutch strings', () => {
        render(<I18nProvider><span /></I18nProvider>);
        const t = i18n.getFixedT('nl', 'respondent');
        expect(deletionStatusLabel('declined', 'identity_not_verified', '3-1-2026', t)).toBe('Niet verwijderd: uw identiteit kon niet worden vastgesteld');
        expect(deletionStatusLabel('success', null, '3-1-2026', t)).toBe('Verwijderd (3-1-2026)');
        expect(deletionStatusLabel('pending', null, '3-1-2026', t)).toBe('Verwijdering aangevraagd');
    });
});
