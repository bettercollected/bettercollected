// The Availability status line of a form's settings, in English and Dutch.
import React from 'react';

import { render, screen } from '@testing-library/react';
import i18n from 'i18next';
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';

import '@app/shared/hocs/i18n-provider';
import { axeViolations } from '@app/test/axe';

import FormAvailabilityStatus from './form-availability-status';

import commonNl from '../../../public/locales/nl/common.json';

const NOW = new Date('2026-11-02T12:00:00Z');
const form = (settings: object = {}, extra: object = {}) => ({ formId: 'f1', isPublished: true, responses: 37, settings: { provider: 'self', ...settings }, ...extra }) as any;
const line = () => screen.getByTestId('availability-status');

beforeAll(() => {
    i18n.addResourceBundle('nl', 'common', commonNl, true, true);
    vi.useFakeTimers({ toFake: ['Date'] });
    vi.setSystemTime(NOW);
});

afterEach(async () => {
    await i18n.changeLanguage('en');
});

describe('the availability status line', () => {
    it('says a form that is not published is not open to respondents', () => {
        render(<FormAvailabilityStatus form={form({}, { isPublished: false })} />);
        expect(line().textContent).toContain('Not published');
        expect(line().textContent).toContain('respondents cannot open it yet');
    });

    it('says open, with the number of responses', () => {
        render(<FormAvailabilityStatus form={form()} />);
        expect(line().textContent).toContain('Open');
        expect(line().textContent).toContain('37 responses');
        expect(line().textContent).not.toContain('closes');
    });

    it('says when it closes and how far the limit is', () => {
        render(<FormAvailabilityStatus form={form({ formCloseDate: '2026-12-12T17:00:00Z', responseLimit: 100 })} />);
        expect(line().textContent).toMatch(/Open.*closes 12 December 2026.*37 of 100 responses/);
    });

    it('says not open yet with the open date', () => {
        render(<FormAvailabilityStatus form={form({ formOpenDate: '2026-12-03T08:00:00Z' })} />);
        expect(line().textContent).toMatch(/Not open yet.*opens 3 December 2026/);
    });

    it('says closed since the close date', () => {
        render(<FormAvailabilityStatus form={form({ formCloseDate: '2026-11-01T17:00:00Z' })} />);
        expect(line().textContent).toMatch(/Closed.*since 1 November 2026.*37 responses/);
    });

    it('says full when the limit is reached', () => {
        render(<FormAvailabilityStatus form={form({ responseLimit: 37 })} />);
        expect(line().textContent).toContain('Full');
        expect(line().textContent).toContain('reached the limit of 37 responses');
    });

    it('is Dutch in Dutch, with the Dutch plural', async () => {
        await i18n.changeLanguage('nl');
        const { unmount } = render(<FormAvailabilityStatus form={form({ formCloseDate: '2026-12-12T17:00:00Z', responseLimit: 100 })} />);
        expect(line().textContent).toMatch(/Open.*sluit op 12 december 2026.*37 van 100 reacties/);
        unmount();
        render(<FormAvailabilityStatus form={form({}, { responses: 1 })} />);
        expect(line().textContent).toContain('1 reactie');
        expect(line().textContent).not.toContain('1 reacties');
    });

    it('is a polite live region named for what it is, and passes axe', async () => {
        render(<FormAvailabilityStatus form={form()} />);
        expect(screen.getByRole('status', { name: 'Availability now' })).toBe(line());
        expect(await axeViolations(document, { page: false })).toEqual([]);
    });
});
