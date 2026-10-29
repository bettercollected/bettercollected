import { act, fireEvent, render, screen } from '@testing-library/react';
import i18n from 'i18next';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
import '@app/shared/hocs/i18n-provider';

import AnswerRulesSettings from './answer-rules-settings';

const field = (validations: StandardFormFieldDto['validations'] = {}, type = FieldTypes.SHORT_TEXT): StandardFormFieldDto => ({ id: 'q', index: 0, type, title: 'Name', validations, properties: {} });
const box = () => screen.getByLabelText('Regular expression') as HTMLInputElement;
const type = (value: string) => fireEvent.change(box(), { target: { value } });

afterEach(async () => {
    await act(() => i18n.changeLanguage('en'));
});

describe('the custom pattern box', () => {
    it('says why an unsafe pattern is refused, and does not save it', () => {
        const onChange = vi.fn();
        render(<AnswerRulesSettings field={field()} onChange={onChange} />);
        type('^(a+)+$');
        expect(screen.getByRole('alert')).toHaveTextContent('Not saved. A repeated group inside a repeated group, such as (a+)+, can take a browser very long to check.');
        expect(box()).toHaveAttribute('aria-invalid', 'true');
        expect(box().getAttribute('aria-describedby')).toContain(screen.getByRole('alert').id);
        expect(onChange).toHaveBeenLastCalledWith({ regex: undefined });
        expect(onChange).not.toHaveBeenCalledWith({ regex: '^(a+)+$' });
    });

    it('saves a safe pattern and takes the error away', () => {
        const onChange = vi.fn();
        render(<AnswerRulesSettings field={field()} onChange={onChange} />);
        type('^(a+)+$');
        type('^[a-z]+( [a-z]+)*$');
        expect(screen.queryByRole('alert')).toBeNull();
        expect(box()).not.toHaveAttribute('aria-invalid');
        expect(onChange).toHaveBeenLastCalledWith({ regex: '^[a-z]+( [a-z]+)*$' });
    });

    it('still saves a pattern that does not compile while it is typed (it is not a hazard)', () => {
        const onChange = vi.fn();
        render(<AnswerRulesSettings field={field()} onChange={onChange} />);
        type('(a+');
        expect(screen.queryByRole('alert')).toBeNull();
        expect(onChange).toHaveBeenLastCalledWith({ regex: '(a+' });
    });

    it('points out a pattern the form already holds: kept, but skipped by respondents', () => {
        render(<AnswerRulesSettings field={field({ regex: '^(a|aa)+$' })} onChange={() => {}} />);
        expect(screen.getByRole('alert')).toHaveTextContent("Saved earlier: respondents' browsers skip this pattern and the server still checks it.");
        expect(screen.getByRole('alert')).toHaveTextContent('(a|aa)+');
    });

    it('speaks Dutch', async () => {
        await act(() => i18n.changeLanguage('nl'));
        render(<AnswerRulesSettings field={field()} onChange={() => {}} />);
        type('^(a+)+$');
        expect(screen.getByRole('alert')).toHaveTextContent('Niet opgeslagen. Een herhaalde groep binnen een herhaalde groep, zoals (a+)+, kan een browser erg lang bezighouden.');
    });

    it('also points out an unsafe pattern an import left on a number question', () => {
        render(<AnswerRulesSettings field={field({ regex: '^(\\d+)+$' }, FieldTypes.NUMBER)} onChange={() => {}} />);
        expect(screen.getByRole('alert')).toHaveTextContent('Saved earlier');
    });
});
