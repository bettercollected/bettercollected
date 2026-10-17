import React from 'react';

import { render, screen } from '@testing-library/react';
import { Provider } from 'jotai';
import { Provider as ReduxProvider } from 'react-redux';
import { describe, expect, it, vi } from 'vitest';

import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import useFormFieldsAtom from '@app/store/jotai/field-selectors';
import { store } from '@app/store/store';

import SlideBuilder from './slide-builder';

vi.mock('next/navigation', () => ({
    usePathname: () => '/acme/dashboard/forms/f1/edit',
    useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
    useSearchParams: () => new URLSearchParams()
}));
vi.mock('@app/views/molecules/rich-text-editor', () => ({
    RichTextEditor: ({ field }: { field: StandardFormFieldDto }) => <div data-testid={`editor-${field.id}`} />
}));
vi.mock('@app/views/organism/form-builder/fields/render-field', () => ({ default: () => null }));
vi.mock('@app/views/molecules/form-builder/plain-language-hints', () => ({ default: () => null }));
vi.mock('@app/lib/hooks/use-form-logo', () => ({ useBuilderFormLogo: () => null }));

const q = (id: string, index: number, type = FieldTypes.SHORT_TEXT): StandardFormFieldDto => ({ id, index, type, title: id });
const page = (id: string, index: number, fields: StandardFormFieldDto[], show?: boolean): StandardFormFieldDto => ({ id, index, type: FieldTypes.SLIDE, properties: { fields, ...(show ? { showQuestionNumbers: true } : {}) } });

function Canvas({ pages }: { pages: StandardFormFieldDto[] }) {
    const atom = useFormFieldsAtom();
    React.useEffect(() => {
        atom.initFormFields(pages);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);
    const slide = atom.formFields[1];
    if (!slide || slide.id !== pages[1].id) return null;
    return <SlideBuilder slide={slide} />;
}

const renderCanvas = (pages: StandardFormFieldDto[]) =>
    render(
        <ReduxProvider store={store}>
            <Provider>
                <Canvas pages={pages} />
            </Provider>
        </ReduxProvider>
    );

describe('question numbers on the builder canvas', () => {
    it('match what respondents see: page.n, questions only', async () => {
        renderCanvas([page('p1', 0, [q('a', 0)], true), page('p2', 1, [q('b', 0), q('t', 1, FieldTypes.TEXT), q('c', 2)], true)]);
        await screen.findByTestId('editor-b');
        expect(screen.getAllByTestId('canvas-question-number').map((n) => n.textContent)).toEqual(['2.1', '2.2']);
    });

    it('none when numbering is off', async () => {
        renderCanvas([page('p1', 0, [q('a', 0)]), page('p2', 1, [q('b', 0)])]);
        await screen.findByTestId('editor-b');
        expect(screen.queryAllByTestId('canvas-question-number')).toHaveLength(0);
    });
});
