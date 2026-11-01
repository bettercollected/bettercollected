// Layout containers on the respondent page (panel, field set, tabs): the
// ARIA patterns, what hides them, and what happens when a question inside a
// closed panel or another tab has a problem (the container opens, says so,
// and focus lands on the question: WCAG 2.1.1, 3.3.1, 4.1.2, 4.1.3).
import React from 'react';

import { act, fireEvent, render, screen, within } from '@testing-library/react';
import { Provider } from 'jotai';
import { Provider as ReduxProvider } from 'react-redux';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ThemeColors } from '@app/constants/theme';
import { FieldTypes, LayoutContainer, StandardFormFieldDto } from '@app/models/dtos/form';
import '@app/shared/hocs/i18n-provider';
import { setForm } from '@app/store/forms/slice';
import { useFormState } from '@app/store/jotai/form';
import { useResponderState } from '@app/store/jotai/responder-form-state';
import { store } from '@app/store/store';

import Form from './form';

vi.mock('next/navigation', () => ({
    usePathname: () => '/acme/forms/f1',
    useRouter: () => ({ push: vi.fn() })
}));
vi.mock('@app/views/organism/form-builder/fields/render-field', () => ({
    RenderImage: () => null,
    default: () => null
}));
vi.mock('framer-motion', async (importOriginal) => ({
    ...(await importOriginal<typeof import('framer-motion')>()),
    AnimatePresence: ({ children }: { children: React.ReactNode }) => <>{children}</>
}));

const question = (id: string, title: string, required = false, properties: StandardFormFieldDto['properties'] = {}): StandardFormFieldDto => ({
    id,
    index: 0,
    type: FieldTypes.SHORT_TEXT,
    title,
    properties: { fields: [], ...properties },
    validations: { required }
});
const panel = (id: string, title: string, fields: string[], extra: Partial<LayoutContainer> = {}): LayoutContainer => ({ id, type: 'panel', title, fields, ...extra });
const tabs = (id: string, ...lists: Array<[string, string[]]>): LayoutContainer => ({ id, type: 'tabs', tabs: lists.map(([title, fields], i) => ({ id: `${id}t${i + 1}`, title, fields })) });

function Page() {
    const { responderState, setResponderState } = useResponderState();
    const { updateFormTheme } = useFormState();
    React.useEffect(() => {
        updateFormTheme(
            ThemeColors.find((theme) => theme.title === 'Default')!,
            { undoable: false }
        );
        setResponderState({ ...responderState, currentSlide: 0, prevActiveSlide: 0 });
    }, []);
    return <Form isPreviewMode />;
}

const open = (fields: StandardFormFieldDto[], containers: LayoutContainer[]) => {
    fields.forEach((field, index) => (field.index = index));
    store.dispatch(setForm({ formId: `layout-${Math.random()}`, title: 'Survey', fields: [{ id: 's1', index: 0, type: FieldTypes.SLIDE, title: '', properties: { fields, containers } }] } as any));
    return render(
        <ReduxProvider store={store}>
            <Provider>
                <Page />
            </Provider>
        </ReduxProvider>
    );
};

// The input reports its value after a 300 ms debounce (FieldInputWrapper).
const type = async (id: string, value: string) => {
    act(() => void fireEvent.change(document.getElementById(`input-field-${id}`)!, { target: { value } }));
    await act(() => new Promise((resolve) => setTimeout(resolve, 350)));
};

const submit = () => act(() => void fireEvent.click(screen.getByRole('button', { name: 'Submit response' })));

describe('layout containers on the respondent page', () => {
    beforeEach(() => {
        window.PUBLIC_CONFIG = { HTTP_SCHEME: 'http://', FORM_DOMAIN: 'localhost:3000' } as any;
        Element.prototype.scrollIntoView = vi.fn();
        window.history.replaceState(null, '', '/acme/forms/f1?lang=en');
    });
    afterEach(() => window.history.replaceState(null, '', '/'));

    it('shows a panel as a disclosure: a button in a heading that opens and closes it', async () => {
        open([question('a', 'First name'), question('b', 'Last name'), question('c', 'Outside')], [panel('c1', 'Contact details', ['a', 'b'])]);
        const button = await screen.findByRole('button', { name: /Contact details/ });
        expect(button).toHaveAttribute('aria-expanded', 'true');
        expect(button.closest('h2')).not.toBeNull();
        expect(screen.getByRole('textbox', { name: 'First name' })).toBeVisible();
        act(() => void fireEvent.click(button));
        expect(button).toHaveAttribute('aria-expanded', 'false');
        expect(screen.queryByRole('textbox', { name: 'First name' })).toBeNull();
        expect(screen.getByRole('textbox', { name: 'Outside' })).toBeVisible();
        // the button controls the body it opens
        expect(document.getElementById(button.getAttribute('aria-controls')!)).toHaveAttribute('hidden');
        act(() => void fireEvent.click(button));
        expect(screen.getByRole('textbox', { name: 'First name' })).toBeVisible();
    });

    it('starts a panel the creator collapsed closed, and keeps what was typed while it is closed', async () => {
        open([question('a', 'First name')], [panel('c1', 'More', ['a'], { collapsed: true })]);
        const button = await screen.findByRole('button', { name: /More/ });
        expect(button).toHaveAttribute('aria-expanded', 'false');
        act(() => void fireEvent.click(button));
        const input = screen.getByRole('textbox', { name: 'First name' });
        act(() => void fireEvent.change(input, { target: { value: 'Ada' } }));
        act(() => void fireEvent.click(button));
        act(() => void fireEvent.click(button));
        expect(screen.getByRole('textbox', { name: 'First name' })).toHaveValue('Ada');
    });

    it('shows a field set as a group named by its legend', async () => {
        open([question('a', 'Street'), question('b', 'City')], [{ id: 'c1', type: 'fieldset', title: 'Billing address', fields: ['a', 'b'] }]);
        const group = await screen.findByRole('group', { name: 'Billing address' });
        expect(group.tagName).toBe('FIELDSET');
        expect(within(group).getByRole('textbox', { name: 'Street' })).toBeVisible();
    });

    it('opens a closed panel that holds the first problem, says so and puts focus on it', async () => {
        open([question('a', 'Your name', true), question('b', 'Reason', true)], [panel('c1', 'Details', ['b'], { collapsed: true })]);
        const button = await screen.findByRole('button', { name: /Details/ });
        expect(button).toHaveAttribute('aria-expanded', 'false');
        await screen.findByRole('textbox', { name: /Your name/ });
        // the first problem is outside: focus goes there, the panel stays closed but says what is in it
        submit();
        expect(document.activeElement).toBe(screen.getByRole('textbox', { name: /Your name/ }));
        expect(button).toHaveAttribute('aria-expanded', 'false');
        expect(button).toHaveTextContent('1 question needs attention');
        // once it is the first problem the panel opens
        await type('a', 'Ada');
        submit();
        expect(button).toHaveAttribute('aria-expanded', 'true');
        expect(document.activeElement).toBe(screen.getByRole('textbox', { name: /Reason/ }));
        expect(document.querySelector('[data-layout-container="c1"] [role="status"]')).toHaveTextContent('Opened "Details": it has a question that needs attention.');
    });

    it('shows tabs with the tabs pattern: roving focus, arrow keys, Home and End', async () => {
        open([question('a', 'Home phone'), question('b', 'Work phone'), question('c', 'Mobile')], [tabs('c1', ['Home', ['a']], ['Work', ['b']], ['Other', ['c']])]);
        const list = await screen.findByRole('tablist');
        const [home, work, other] = within(list).getAllByRole('tab');
        expect(home).toHaveAttribute('aria-selected', 'true');
        expect(home).toHaveAttribute('tabindex', '0');
        expect(work).toHaveAttribute('tabindex', '-1');
        expect(screen.getByRole('tabpanel', { name: 'Home' })).toBeVisible();
        expect(screen.getByRole('textbox', { name: 'Home phone' })).toBeVisible();
        expect(screen.queryByRole('textbox', { name: 'Work phone' })).toBeNull();
        home.focus();
        act(() => void fireEvent.keyDown(home, { key: 'ArrowRight' }));
        expect(work).toHaveAttribute('aria-selected', 'true');
        expect(document.activeElement).toBe(work);
        expect(screen.getByRole('tabpanel', { name: 'Work' })).toBeVisible();
        act(() => void fireEvent.keyDown(work, { key: 'End' }));
        expect(other).toHaveAttribute('aria-selected', 'true');
        act(() => void fireEvent.keyDown(other, { key: 'ArrowRight' }));
        expect(home).toHaveAttribute('aria-selected', 'true');
        act(() => void fireEvent.keyDown(home, { key: 'ArrowLeft' }));
        expect(other).toHaveAttribute('aria-selected', 'true');
        act(() => void fireEvent.keyDown(other, { key: 'Home' }));
        expect(home).toHaveAttribute('aria-selected', 'true');
        expect(home).toHaveAttribute('aria-controls', screen.getByRole('tabpanel', { name: 'Home' }).id);
    });

    it('shows the tab that holds the first problem, and says so', async () => {
        open([question('a', 'Home phone'), question('b', 'Work phone', true)], [tabs('c1', ['Home', ['a']], ['Work', ['b']])]);
        const work = await screen.findByRole('tab', { name: /Work/ });
        expect(work).toHaveAttribute('aria-selected', 'false');
        submit();
        expect(work).toHaveAttribute('aria-selected', 'true');
        expect(document.activeElement).toBe(screen.getByRole('textbox', { name: /Work phone/ }));
        expect(document.querySelector('[data-layout-container="c1"] [role="status"]')).toHaveTextContent('Showing the tab "Work": it has a question that needs attention.');
    });

    it('offers no tab whose questions are all hidden, and no container with nothing to show', async () => {
        const hidden = { action: 'SHOW', operator: 'AND', conditions: [{ fieldId: 'gate', fieldType: FieldTypes.SHORT_TEXT, comparison: 'IS_EQUAL', value: 'yes' }] } as any;
        const fields = [question('gate', 'Gate'), question('a', 'Home phone'), question('b', 'Work phone', false, { logic: hidden }), question('c', 'Side', false)];
        open(fields, [tabs('c1', ['Home', ['a']], ['Work', ['b']]), panel('c2', 'Hidden panel', ['c'], { logic: hidden })]);
        await screen.findByRole('tablist');
        expect(screen.getAllByRole('tab')).toHaveLength(1);
        expect(screen.queryByRole('button', { name: /Hidden panel/ })).toBeNull();
        expect(screen.queryByRole('textbox', { name: 'Side' })).toBeNull();
        await type('gate', 'yes');
        expect(screen.getAllByRole('tab')).toHaveLength(2);
        expect(screen.getByRole('button', { name: /Hidden panel/ })).toBeVisible();
    });

    it('says it again when a closed panel or other tab has to be opened a second time, not once only', async () => {
        open([question('a', 'Home phone'), question('b', 'Work phone', true)], [tabs('c1', ['Home', ['a']], ['Work', ['b']])]);
        const work = await screen.findByRole('tab', { name: /Work/ });
        const status = () => document.querySelector('[data-layout-container="c1"] [role="status"]')!;
        submit();
        expect(status()).toHaveTextContent('Showing the tab "Work"');
        // the respondent goes back to the first tab by hand: the old message goes with it
        act(() => void fireEvent.click(screen.getByRole('tab', { name: /Home/ })));
        expect(status()).toHaveTextContent('');
        expect(work).toHaveAttribute('aria-selected', 'false');
        submit();
        expect(work).toHaveAttribute('aria-selected', 'true');
        expect(status()).toHaveTextContent('Showing the tab "Work"');
    });

    it('names several tab strips on a page apart, and makes a panel with nothing to tab to a tab stop', async () => {
        const text = (id: string, title: string): StandardFormFieldDto => ({ ...question(id, title), type: FieldTypes.TEXT });
        open([text('a', 'Intro one'), text('b', 'Intro two'), question('c', 'Phone'), question('d', 'Mobile')], [tabs('c1', ['One', ['a']], ['Two', ['b']]), tabs('c2', ['Three', ['c']], ['Four', ['d']])]);
        const lists = await screen.findAllByRole('tablist');
        expect(lists.map((list) => list.getAttribute('aria-label'))).toEqual(['Sections 1', 'Sections 2']);
        // only text in this tab: nothing inside can take focus, so the panel itself does
        expect(screen.getByRole('tabpanel', { name: 'One' })).toHaveAttribute('tabindex', '0');
        expect(screen.getByRole('tabpanel', { name: 'Three' })).not.toHaveAttribute('tabindex');
    });

    it('calls a single tab strip just that', async () => {
        open([question('a', 'Home phone'), question('b', 'Work phone')], [tabs('c1', ['Home', ['a']], ['Work', ['b']])]);
        expect(await screen.findByRole('tablist', { name: 'Sections' })).toBeInTheDocument();
    });
});
