import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { useTranslation } from 'react-i18next';
import I18nProvider from '@app/shared/hocs/i18n-provider';

function Probe() {
    const { t } = useTranslation();
    return <span>{t('MEMBERS.DEFAULT')} / {t('FORM.RESPONSES')}</span>;
}

describe('i18n after next-i18next removal', () => {
    it('t() resolves translations through the app provider (no raw keys)', () => {
        render(<I18nProvider><Probe /></I18nProvider>);
        expect(screen.getByText(/Members/)).toBeDefined();
        expect(screen.queryByText(/MEMBERS\.DEFAULT/)).toBeNull();
    });
});
