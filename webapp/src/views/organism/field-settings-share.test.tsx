import React from 'react';

import { cleanup, render, screen } from '@testing-library/react';
import { Provider } from 'jotai';
import { Provider as ReduxProvider } from 'react-redux';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import { useActiveFieldComponent, useActiveSlideComponent } from '@app/store/jotai/active-builder-component';
import useFormFieldsAtom from '@app/store/jotai/field-selectors';
import { store } from '@app/store/store';

import FieldSettings from './field-settings';

// What the server says about option sources (its OPTION_SOURCES_ENABLED).
const served = vi.hoisted(() => ({ optionSourcesEnabled: false }));
vi.mock('@app/lib/hooks/use-workspace-permissions', () => ({ useWorkspacePermissions: () => ({ optionSourcesEnabled: served.optionSourcesEnabled }) }));
afterEach(() => {
    served.optionSourcesEnabled = false;
    cleanup();
});

function Selected({ field }: { field: StandardFormFieldDto }) {
    const builder = useFormFieldsAtom();
    const { setActiveSlideComponent } = useActiveSlideComponent();
    const { setActiveFieldComponent } = useActiveFieldComponent();
    React.useEffect(() => {
        builder.initFormFields([{ id: 'page-1', index: 0, type: FieldTypes.SLIDE, properties: { fields: [field] } } as StandardFormFieldDto]);
        setActiveSlideComponent({ id: 'page-1', index: 0 });
        setActiveFieldComponent({ id: 'q', index: 0 });
    }, []);
    return <FieldSettings />;
}

const question = (type: FieldTypes, shareAsChoices?: boolean): StandardFormFieldDto => ({ id: 'q', index: 0, type, title: 'Question', properties: { shareAsChoices } }) as StandardFormFieldDto;

const renderSettings = (field: StandardFormFieldDto) =>
    render(
        <ReduxProvider store={store}>
            <Provider>
                <Selected field={field} />
            </Provider>
        </ReduxProvider>
    );

describe('the "answers may be shown as choices" switch', () => {
    it('shows for a question that can share, on or off, while the server takes sources', async () => {
        served.optionSourcesEnabled = true;
        renderSettings(question(FieldTypes.SHORT_TEXT, true));
        expect(await screen.findByRole('switch', { name: /SOURCES.SHARE_LABEL|Answers may be shown as choices/ })).toBeChecked();
    });

    it('stays, with a reason, when the setting is on and the question stopped qualifying (its type changed)', async () => {
        served.optionSourcesEnabled = true;
        renderSettings(question(FieldTypes.EMAIL, true));
        const toggle = await screen.findByRole('switch', { name: /SOURCES.SHARE_LABEL|Answers may be shown as choices/ });
        expect(toggle).toBeChecked();
        expect(toggle).toBeEnabled();
        expect(screen.getByText(/SOURCES.SHARE_NO_LONGER|can no longer share/)).toBeInTheDocument();
    });

    it('stays when the setting is on and the server no longer takes sources: it can still be turned off', async () => {
        renderSettings(question(FieldTypes.SHORT_TEXT, true));
        expect(await screen.findByRole('switch', { name: /SOURCES.SHARE_LABEL|Answers may be shown as choices/ })).toBeEnabled();
    });

    it('is not offered for a question that cannot share when the setting is off', async () => {
        served.optionSourcesEnabled = true;
        renderSettings(question(FieldTypes.EMAIL));
        await screen.findByText('Question');
        expect(screen.queryByRole('switch', { name: /SOURCES.SHARE_LABEL|Answers may be shown as choices/ })).toBeNull();
    });
});
