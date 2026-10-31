import React from 'react';

import { render } from '@testing-library/react';
import { Provider } from 'jotai';
import { Provider as ReduxProvider } from 'react-redux';
import { describe, expect, it, vi } from 'vitest';

import { FieldTypes, StandardFormFieldDto } from '@app/models/dtos/form';
// Registers the respondent translations, as the app layout does.
import '@app/shared/hocs/i18n-provider';
import { store } from '@app/store/store';

import { useQuestionLabel } from './question-label-context';
import QuestionWrapper from './question-wrapper';

const LabelledProbe = () => <input {...useQuestionLabel().control} />;

// RenderImage drags in the whole builder field registry; irrelevant here.
vi.mock('@app/views/organism/form-builder/fields/render-field', () => ({
    RenderImage: () => null,
    default: () => null
}));

const field = (overrides: Partial<StandardFormFieldDto> = {}): StandardFormFieldDto => ({ id: 'f1', index: 0, type: FieldTypes.SHORT_TEXT, title: 'Your name?', ...overrides });

const markup = (f: StandardFormFieldDto) =>
    render(
        <ReduxProvider store={store}>
            <Provider>
                <QuestionWrapper field={f}>
                    <LabelledProbe />
                </QuestionWrapper>
            </Provider>
        </ReduxProvider>
    ).container.innerHTML;

describe('QuestionWrapper without field rules', () => {
    it('renders an optional question exactly as before rules existed', () => {
        expect(markup(field())).toMatchInlineSnapshot(
            `"<div class="relative flex flex-col gap-1 lg:gap-2" data-question-wrapper="true" id="f1"><div class="relative"><div class="relative flex flex-wrap items-baseline gap-x-2.5"><div class="text-base font-semibold leading-snug lg:text-lg lg:leading-7 form-title-face [&amp;_p]:inline [&amp;_h1]:text-[32px] [&amp;_h1]:font-bold [&amp;_h1]:leading-tight [&amp;_h2]:text-[26px] [&amp;_h2]:font-bold [&amp;_h2]:leading-tight [&amp;_h3]:text-[21px] [&amp;_h3]:font-semibold [&amp;_h3]:leading-snug [&amp;_h1+*]:mt-2 [&amp;_h2+*]:mt-2 [&amp;_h3+*]:mt-1" style="color: rgb(16, 24, 40);"><div id="q-title-f1" class="contents"><p><strong>Your name?</strong></p></div></div><span class="form-note-accent text-[13px] font-normal text-black-700">Optional</span></div></div><input aria-labelledby="q-title-f1"></div>"`
        );
    });

    it('renders a required question with a description exactly as before rules existed', () => {
        expect(markup(field({ id: 'f2', description: 'As on your passport', validations: { required: true } }))).toMatchInlineSnapshot(
            `"<div class="relative flex flex-col gap-1 lg:gap-2" data-question-wrapper="true" id="f2"><div class="relative"><div class="relative flex flex-wrap items-baseline gap-x-2.5"><div class="text-base font-semibold leading-snug lg:text-lg lg:leading-7 form-title-face [&amp;_p]:inline [&amp;_h1]:text-[32px] [&amp;_h1]:font-bold [&amp;_h1]:leading-tight [&amp;_h2]:text-[26px] [&amp;_h2]:font-bold [&amp;_h2]:leading-tight [&amp;_h3]:text-[21px] [&amp;_h3]:font-semibold [&amp;_h3]:leading-snug [&amp;_h1+*]:mt-2 [&amp;_h2+*]:mt-2 [&amp;_h3+*]:mt-1" style="color: rgb(16, 24, 40);"><div id="q-title-f2" class="contents"><p><strong>Your name?</strong></p></div><span aria-hidden="true" style="color: rgb(196, 61, 61);"> *</span><span id="q-required-f2" class="sr-only"> (required)</span></div></div><div id="q-desc-f2" class="mt-1.5 max-w-[62ch] text-[15px] leading-relaxed text-black-700">As on your passport</div></div><input aria-labelledby="q-title-f2" aria-describedby="q-desc-f2" aria-required="true"></div>"`
        );
    });
});
