import React from 'react';

import { render } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { FormTheme, ThemeColors } from '@app/constants/theme';

import Choice, { choiceRowStyle, showsOptionKeys } from './choice';
import ChoiceRadioGroup from './choice-radio-group';

/**
 * Answer options keep the look they have. A theme without a `choiceKeys` key (every
 * preset and stored theme that exists today) draws its single-answer group, its
 * checkboxes and its rows exactly as before: the markup, the row styles and which
 * themes show option keys are pinned for each of them, so adding a key to the model
 * moves none of them. Written before the key existed and green without it.
 */

const STORED_OCEAN: FormTheme = { title: 'Ocean', primary: '#111827', secondary: '#1D4ED8', tertiary: '#2563EB', accent: '#DBEAFE', titleFont: null, bodyFont: null, radius: null, buttonStyle: null, highlight: null, selection: null };
const STORED_ROUND: FormTheme = { title: 'Mine', primary: '#16261F', secondary: '#1E4D3B', tertiary: '#7D8C84', accent: '#FFFFFF', radius: 'round', buttonStyle: 'pill', highlight: '#A3305A' };

const THEMES: Array<[string, FormTheme | undefined]> = [['no theme', undefined], ['stored Ocean', STORED_OCEAN], ['stored round', STORED_ROUND], ...ThemeColors.filter((theme) => theme.choiceKeys == null).map((theme) => [theme.title, theme] as [string, FormTheme])];

const options = ['Every week', 'Every month', 'A few times a year'].map((label, index) => ({ value: `v${index}`, label, key: `k${index}` }));

describe.each(THEMES)('answer options on %s', (_name, theme) => {
    it('draws the same single-answer group', () => {
        const { container } = render(<ChoiceRadioGroup options={options} value="v1" onChange={() => {}} theme={theme} labelledBy="q" />);
        expect(container.innerHTML).toMatchSnapshot();
    });

    it('draws the same checkboxes', () => {
        const { container } = render(
            <div>
                {options.map((option, index) => (
                    <Choice key={option.key} kind="checkbox" isSelected={index === 1} theme={theme} choice={{ id: option.key, value: option.label }} index={index} keyHint={showsOptionKeys(theme) ? String.fromCharCode(65 + index) : undefined} onClick={() => {}} />
                ))}
            </div>
        );
        expect(container.innerHTML).toMatchSnapshot();
    });

    it('dresses a row the same, at rest and chosen, and shows keys for the same themes', () => {
        expect({ rest: choiceRowStyle(theme, false), chosen: choiceRowStyle(theme, true), keys: showsOptionKeys(theme) }).toMatchSnapshot();
    });
});
