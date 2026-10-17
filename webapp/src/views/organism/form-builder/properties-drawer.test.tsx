import React from 'react';

import { act, fireEvent, render, screen, within } from '@testing-library/react';
import { Provider } from 'jotai';
import { Provider as ReduxProvider } from 'react-redux';
import { describe, expect, it, vi } from 'vitest';

import { useInspectorEscape } from '@app/lib/hooks/use-inspector-escape';
import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import { FormSlideLayout } from '@app/models/enums/form';
import { useActiveFieldComponent, useActiveSlideComponent } from '@app/store/jotai/active-builder-component';
import useFormFieldsAtom from '@app/store/jotai/field-selectors';
import { usePropertiesTab } from '@app/store/jotai/properties-tab';
import { store } from '@app/store/store';

import PropertiesDrawer, { pageCrumbLabel } from './properties-drawer';

vi.mock('next/navigation', () => ({
    usePathname: () => '/acme/dashboard/forms/f1/edit',
    useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
    useSearchParams: () => new URLSearchParams()
}));
// Tabs that are not what is tested here.
vi.mock('@app/views/organism/form-builder/ai-chat-tab', () => ({ default: () => <div>AI assistant</div> }));
vi.mock('@app/views/organism/form-builder/page-design-tab', () => ({ default: () => <div>Design settings</div> }));
vi.mock('@app/views/molecules/form-builder/trust-settings-editor', () => ({ default: () => <div>Trust settings</div> }));
vi.mock('@app/views/molecules/form-builder/hidden-fields-editor', () => ({ default: () => <div>Hidden fields</div> }));

const question = (id: string, index: number, title: string, extra: Partial<StandardFormFieldDto> = {}): StandardFormFieldDto => ({ id, index, type: FieldTypes.SHORT_TEXT, title, ...extra });
const page = (id: string, index: number, fields: StandardFormFieldDto[]): StandardFormFieldDto => ({ id, index, type: FieldTypes.SLIDE, properties: { layout: FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND, fields } });

let builder: ReturnType<typeof useFormFieldsAtom> | null = null;
let tab: ReturnType<typeof usePropertiesTab> | null = null;
let selection: ReturnType<typeof useActiveFieldComponent> | null = null;

function Builder({ pages, field }: { pages: StandardFormFieldDto[]; field?: { id: string; index: number } }) {
    builder = useFormFieldsAtom();
    tab = usePropertiesTab();
    selection = useActiveFieldComponent();
    const { setActiveSlideComponent } = useActiveSlideComponent();
    useInspectorEscape();
    const [ready, setReady] = React.useState(false);
    React.useEffect(() => {
        builder!.initFormFields(pages);
        setActiveSlideComponent({ id: pages[1]?.id ?? pages[0].id, index: pages[1] ? 1 : 0 });
        if (field) selection!.setActiveFieldComponent(field);
        setReady(true);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);
    return ready ? <PropertiesDrawer /> : null;
}

const twoPages = () => [page('p1', 0, [question('a', 0, 'Your name')]), page('p2', 1, [question('b', 0, 'Postcode', { validations: { required: true } }), question('c', 1, 'Comments', { type: FieldTypes.LONG_TEXT })])];

const renderBuilder = (field?: { id: string; index: number }) =>
    render(
        <ReduxProvider store={store}>
            <Provider>
                <Builder pages={twoPages()} field={field} />
            </Provider>
        </ReduxProvider>
    );

const crumbs = () => within(screen.getByRole('navigation', { name: 'Settings location' }));
const pressEscape = (target: Element | Window = window, init: KeyboardEventInit = {}) => act(() => void fireEvent.keyDown(target, { key: 'Escape', ...init }));

describe('inspector breadcrumb', () => {
    it('says where you are, and each crumb goes to that level', async () => {
        renderBuilder({ id: 'b', index: 0 });
        expect(await screen.findByRole('heading', { name: 'Basics' })).toBeInTheDocument();
        expect(crumbs().getByText('Postcode')).toHaveAttribute('aria-current', 'location');
        expect(crumbs().getByRole('button', { name: 'Form' })).toBeInTheDocument();

        act(() => void fireEvent.click(crumbs().getByRole('button', { name: 'Page 2' })));
        expect(selection!.activeFieldComponent).toBeNull();
        expect(tab!.propertiesTab).toBe('page');
        expect(crumbs().getByText('Page 2')).toHaveAttribute('aria-current', 'location');
        expect(crumbs().queryByText('Postcode')).toBeNull();

        act(() => void fireEvent.click(crumbs().getByRole('button', { name: 'Form' })));
        expect(tab!.propertiesTab).toBe('form');
        expect(crumbs().getByText('Form')).toHaveAttribute('aria-current', 'location');
        expect(screen.getByText('Hidden fields')).toBeInTheDocument();
    });

    it('Escape goes up one level: question → page → form', async () => {
        renderBuilder({ id: 'b', index: 0 });
        await screen.findByRole('heading', { name: 'Basics' });
        pressEscape();
        expect(selection!.activeFieldComponent).toBeNull();
        expect(tab!.propertiesTab).toBe('page');
        pressEscape();
        expect(tab!.propertiesTab).toBe('form');
        pressEscape();
        expect(tab!.propertiesTab).toBe('form');
    });

    it('Escape that a popover, menu or dialog handled is left alone', async () => {
        renderBuilder({ id: 'b', index: 0 });
        await screen.findByRole('heading', { name: 'Basics' });
        // Handled already (Radix and ProseMirror mark it with preventDefault).
        const handled = new KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true });
        handled.preventDefault();
        act(() => void window.dispatchEvent(handled));
        expect(selection!.activeFieldComponent).not.toBeNull();

        // Cancelling a keyboard drag in the outline: dnd-kit's KeyboardSensor
        // handles Escape on the document (before the window) and prevents it.
        const cancelDrag = (event: KeyboardEvent) => event.key === 'Escape' && event.preventDefault();
        document.addEventListener('keydown', cancelDrag);
        pressEscape(document.body);
        document.removeEventListener('keydown', cancelDrag);
        expect(selection!.activeFieldComponent).not.toBeNull();

        // From inside a menu.
        const menu = document.createElement('div');
        menu.setAttribute('role', 'menu');
        const item = document.createElement('button');
        menu.appendChild(item);
        document.body.appendChild(menu);
        pressEscape(item);
        expect(selection!.activeFieldComponent).not.toBeNull();
        menu.remove();

        // While a dialog is open.
        const dialog = document.createElement('div');
        dialog.setAttribute('role', 'dialog');
        dialog.setAttribute('data-state', 'open');
        document.body.appendChild(dialog);
        pressEscape();
        expect(selection!.activeFieldComponent).not.toBeNull();
        dialog.remove();

        pressEscape();
        expect(selection!.activeFieldComponent).toBeNull();
    });

    it('Escape while typing in a page setting does not leave the page', async () => {
        renderBuilder();
        const input = await screen.findByRole('textbox', { name: 'Section title' });
        pressEscape(input);
        expect(tab!.propertiesTab).toBe('page');
    });
});

describe('page tab', () => {
    it('lists the page’s questions to select them, without a second place to edit width or Required', async () => {
        renderBuilder();
        const list = await screen.findByRole('list', { name: 'Questions on this page' });
        expect(within(list).getByText('Required')).toBeInTheDocument();
        expect(screen.queryByRole('combobox', { name: 'Field width' })).toBeNull();
        act(() => void fireEvent.click(within(list).getByRole('button', { name: /Comments/ })));
        expect(selection!.activeFieldComponent).toEqual({ id: 'c', index: 1 });
        expect(crumbs().getByText('Comments')).toHaveAttribute('aria-current', 'location');
    });

    it('the layout picker is a set of real toggle buttons', async () => {
        renderBuilder();
        const group = await screen.findByRole('group', { name: 'Page layout' });
        const centered = within(group).getByRole('button', { name: 'Centered' });
        expect(centered).toHaveAttribute('aria-pressed', 'true');
        const left = within(group).getByRole('button', { name: 'Left aligned' });
        expect(left).toHaveAttribute('aria-pressed', 'false');
        act(() => void fireEvent.click(left));
        expect(builder!.formFields[1].properties?.layout).toBe(FormSlideLayout.SINGLE_COLUMN_NO_BACKGROUND_LEFT_ALIGN);
        expect(within(group).getByRole('button', { name: 'Left aligned' })).toHaveAttribute('aria-pressed', 'true');
    });

    it('the section title writes the page’s own title (the one the canvas bar edits too)', async () => {
        renderBuilder();
        const input = (await screen.findByRole('textbox', { name: 'Section title' })) as HTMLInputElement;
        act(() => void fireEvent.change(input, { target: { value: 'Where you live' } }));
        expect(builder!.formFields[1].properties?.sectionTitle).toBe('Where you live');
        // An edit made elsewhere (the canvas bar) shows here too.
        act(() => builder!.updateSlideSectionTitle(1, 'Your address'));
        expect((screen.getByRole('textbox', { name: 'Section title' }) as HTMLInputElement).value).toBe('Your address');
    });
});

describe('form tab: question numbering', () => {
    it('numbers every page, and says so when only some pages are numbered', async () => {
        renderBuilder();
        await screen.findByRole('group', { name: 'Page layout' });
        act(() => tab!.setPropertiesTab('form'));
        const toggle = screen.getByRole('switch', { name: 'Number questions' });
        expect(toggle).toHaveAttribute('aria-checked', 'false');
        act(() => void fireEvent.click(toggle));
        expect(builder!.formFields.map((p) => p.properties?.showQuestionNumbers)).toEqual([true, true]);
        expect(screen.getByRole('switch', { name: 'Number questions' })).toHaveAttribute('aria-checked', 'true');

        act(() => builder!.updateShowQuestionNumbers(0, false));
        expect(screen.getByRole('switch', { name: 'Number questions' })).toHaveAttribute('aria-checked', 'false');
        expect(screen.getByText(/Some pages are numbered/)).toBeInTheDocument();
    });
});

describe('question panel: answer rules', () => {
    it('edits write the field’s validations, and the summary says what is active', async () => {
        renderBuilder({ id: 'b', index: 0 });
        expect(await screen.findByRole('heading', { name: 'Answer rules' })).toBeInTheDocument();
        act(() => void fireEvent.change(screen.getByLabelText('Max. characters'), { target: { value: '7' } }));
        act(() => void fireEvent.change(screen.getByLabelText('Format'), { target: { value: 'postcode_nl' } }));
        const field = () => builder!.formFields[1].properties!.fields![0];
        expect(field().validations).toEqual({ required: true, maxLength: 7, regex: '^[1-9][0-9]{3} ?[A-Za-z]{2}$' });
        const summary = screen.getByRole('list', { name: 'Active answer rules' });
        expect(within(summary).getByText('Answer is at most 7 characters.')).toBeInTheDocument();
        expect(within(summary).getByText('Answer must be a Dutch postcode, e.g. 1234 AB.')).toBeInTheDocument();

        // Clearing a limit removes it from the model.
        act(() => void fireEvent.change(screen.getByLabelText('Max. characters'), { target: { value: '' } }));
        act(() => void fireEvent.change(screen.getByLabelText('Format'), { target: { value: '' } }));
        expect(field().validations).toEqual({ required: true });
        expect(screen.getByText('No rules: any answer is accepted.')).toBeInTheDocument();
    });

    it('a custom pattern sits under Advanced; contradictory limits are pointed out', async () => {
        renderBuilder({ id: 'c', index: 1 });
        await screen.findByRole('heading', { name: 'Answer rules' });
        act(() => void fireEvent.change(screen.getByLabelText('Regular expression'), { target: { value: '^[A-Z]+$' } }));
        expect(builder!.formFields[1].properties!.fields![1].validations?.regex).toBe('^[A-Z]+$');
        expect((screen.getByLabelText('Format') as HTMLSelectElement).value).toBe('custom');
        act(() => void fireEvent.change(screen.getByLabelText('Min. characters'), { target: { value: '9' } }));
        act(() => void fireEvent.change(screen.getByLabelText('Max. characters'), { target: { value: '3' } }));
        expect(screen.getByText('The minimum length is more than the maximum.')).toBeInTheDocument();
    });

    it('every switch in the panel is named', async () => {
        renderBuilder({ id: 'b', index: 0 });
        await screen.findByRole('heading', { name: 'Basics' });
        screen.getAllByRole('switch').forEach((control) => expect(control).toHaveAccessibleName());
        expect(screen.getByRole('switch', { name: 'Required' })).toHaveAttribute('aria-checked', 'true');
        expect(screen.getByRole('group', { name: 'Width' })).toBeInTheDocument();
        expect(screen.getByRole('button', { name: 'Full width' })).toHaveAttribute('aria-pressed', 'true');
    });
});

describe('pageCrumbLabel', () => {
    it('names an ending by its name, else its title', () => {
        const ending = { id: 'thank-you-page', index: -20 };
        expect(pageCrumbLabel(ending, { name: ' Eligible ', title: 'Welcome aboard' })).toBe('Eligible');
        expect(pageCrumbLabel(ending, { title: 'Welcome aboard' })).toBe('Welcome aboard');
        expect(pageCrumbLabel(ending, {})).toBe('Ending');
        expect(pageCrumbLabel({ id: 'p1', index: 1 })).toBe('Page 2');
    });
});
