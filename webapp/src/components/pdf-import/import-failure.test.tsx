import React from 'react';

import { render, screen } from '@testing-library/react';
import i18n from 'i18next';
import { afterEach, describe, expect, it } from 'vitest';

import '@app/shared/hocs/i18n-provider';
import { IMPORT_ERROR_CODES, START_ERROR_CODES, importErrorCode, startErrorKey } from '@app/utils/pdf-import';

import enBuilder from '../../../public/locales/en/builder.json';
import nlBuilder from '../../../public/locales/nl/builder.json';
import ImportFailure from './import-failure';

const en = enBuilder.PDF_IMPORT as any;
const nl = nlBuilder.PDF_IMPORT as any;

const failed = (over: Record<string, any> = {}) => ({ formId: null, errorCode: 'failed', report: {}, aiConsent: false, ...over });

function keysOf(tree: any, prefix = ''): string[] {
    return Object.entries(tree).flatMap(([k, v]) => (typeof v === 'object' ? keysOf(v, `${prefix}${k}.`) : [`${prefix}${k}`]));
}

afterEach(async () => {
    await i18n.changeLanguage('en');
});

describe('ImportFailure', () => {
    it.each(IMPORT_ERROR_CODES.filter((c) => c !== 'no_questions'))('explains "%s" and what to do next', (code) => {
        render(<ImportFailure data={failed({ errorCode: code })} workspaceName="acme" />);
        const alert = screen.getByRole('alert');
        expect(alert).toHaveTextContent(en.ERROR[code].MESSAGE);
        expect(alert).toHaveTextContent(en.ERROR[code].NEXT);
        // the empty draft is gone: nothing to open, only another try
        expect(screen.getByText(en.DRAFT_REMOVED)).toBeInTheDocument();
        expect(screen.queryByText(en.OPEN_DRAFT)).toBeNull();
        expect(screen.getByText(en.TRY_ANOTHER_FILE).closest('a')).toHaveAttribute('href', '/acme/dashboard/forms/create');
    });

    it('tells an import without AI that scans need AI reading or selectable text', () => {
        render(<ImportFailure data={failed({ errorCode: 'no_questions', report: { notes: ['AI structuring not used: no consent for this import'] } })} workspaceName="acme" />);
        expect(screen.getByRole('alert')).toHaveTextContent(en.ERROR.no_questions.NEXT_WITHOUT_AI);
    });

    it('suggests a clearer file when the AI read the document and still found nothing', () => {
        render(<ImportFailure data={failed({ errorCode: 'no_questions', aiConsent: true })} workspaceName="acme" />);
        const alert = screen.getByRole('alert');
        expect(alert).toHaveTextContent(en.ERROR.no_questions.NEXT);
        expect(alert).not.toHaveTextContent(en.ERROR.no_questions.NEXT_WITHOUT_AI);
    });

    it('links a draft that was kept because the user had changed it', () => {
        render(<ImportFailure data={failed({ formId: 'f1', errorCode: 'timeout' })} workspaceName="acme" />);
        expect(screen.getByText(en.DRAFT_KEPT)).toBeInTheDocument();
        expect(screen.getByText(en.OPEN_DRAFT).closest('a')).toHaveAttribute('href', '/acme/dashboard/forms/f1/edit');
    });

    it('speaks Dutch', async () => {
        await i18n.changeLanguage('nl');
        render(<ImportFailure data={failed({ errorCode: 'encrypted' })} workspaceName="acme" />);
        const alert = screen.getByRole('alert');
        expect(alert).toHaveTextContent(nl.ERROR.encrypted.MESSAGE);
        expect(alert).toHaveTextContent(nl.ERROR.encrypted.NEXT);
        expect(screen.getByText(nl.DRAFT_REMOVED)).toBeInTheDocument();
        expect(screen.getByText(nl.TRY_ANOTHER_FILE)).toBeInTheDocument();
    });

    it('says an interrupted import can simply be tried again', () => {
        render(<ImportFailure data={failed({ errorCode: 'interrupted' })} workspaceName="acme" />);
        expect(screen.getByRole('alert')).toHaveTextContent(/^The import was interrupted\.\s*Please try again\.$/);
        expect(screen.getByText(en.TRY_ANOTHER_FILE).closest('a')).toHaveAttribute('href', '/acme/dashboard/forms/create');
    });

    it('says an interrupted import can simply be tried again, in Dutch', async () => {
        await i18n.changeLanguage('nl');
        render(<ImportFailure data={failed({ errorCode: 'interrupted' })} workspaceName="acme" />);
        expect(screen.getByRole('alert')).toHaveTextContent(/^Het importeren is onderbroken\.\s*Probeer het opnieuw\.$/);
        expect(screen.getByText(nl.TRY_ANOTHER_FILE).closest('a')).toHaveAttribute('href', '/acme/dashboard/forms/create');
    });

    it('never shows the raw server message or a translation key', () => {
        render(<ImportFailure data={failed({ errorCode: 'some_new_code', error: 'Internal detail' } as any)} workspaceName="acme" />);
        const alert = screen.getByRole('alert');
        expect(alert).toHaveTextContent(en.ERROR.failed.MESSAGE);
        expect(alert).not.toHaveTextContent('Internal detail');
        expect(alert).not.toHaveTextContent('PDF_IMPORT');
    });
});

describe('import error codes', () => {
    it('reads older records from report.refused and treats unknown codes as a plain failure', () => {
        expect(importErrorCode({ report: { refused: 'encrypted' } })).toBe('encrypted');
        expect(importErrorCode({ errorCode: 'too_many_pages', report: { refused: 'x' } })).toBe('too_many_pages');
        expect(importErrorCode({ errorCode: 'unsupported_mode' })).toBe('failed');
        expect(importErrorCode({})).toBe('failed');
    });

    it('translates refused uploads it knows and leaves the rest to the server message', () => {
        expect(startErrorKey('import_in_progress')).toBe('PDF_IMPORT.START_ERROR.import_in_progress');
        expect(startErrorKey('daily_limit')).toBe('PDF_IMPORT.START_ERROR.daily_limit');
        expect(startErrorKey('something_else')).toBeNull();
        expect(startErrorKey(undefined)).toBeNull();
        for (const code of START_ERROR_CODES) expect(en.START_ERROR[code]).toBeTruthy();
    });

    it('has every message in English and Dutch', () => {
        expect(keysOf(nl).sort()).toEqual(keysOf(en).sort());
        for (const code of IMPORT_ERROR_CODES) {
            expect(en.ERROR[code].MESSAGE && en.ERROR[code].NEXT).toBeTruthy();
            expect(nl.ERROR[code].MESSAGE && nl.ERROR[code].NEXT).toBeTruthy();
        }
    });
});
