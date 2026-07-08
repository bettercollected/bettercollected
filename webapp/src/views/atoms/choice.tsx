import { Check } from 'lucide-react';
import styled from 'styled-components';

import { FormTheme } from '@app/constants/theme';
import { FieldChoice } from '@app/models/dtos/form';

interface ChoiceProps {
    isSelected?: boolean;
    theme?: FormTheme;
    choice: FieldChoice;
    index: number;
    onClick?: (choiceId: string) => any;
}

const StyledChoiceButton = styled.button<{ $theme: any }>(({ $theme }) => {
    const secondaryColor = $theme?.secondary;
    return {
        '&:hover': {
            borderColor: secondaryColor + '!important'
        },
        // Keyboard users get the same affordance as hover (WCAG 2.4.7) — the
        // options were plain clickable divs with no focus state at all.
        '&:focus-visible': {
            outline: 'none',
            borderColor: secondaryColor + '!important',
            boxShadow: secondaryColor ? `0 0 0 3px ${secondaryColor}40` : undefined
        }
    };
});

export default function Choice({ isSelected, theme, index, choice, onClick }: ChoiceProps) {
    return (
        <StyledChoiceButton
            type="button"
            aria-pressed={isSelected}
            $theme={theme}
            style={{
                background: isSelected ? theme?.tertiary + '55' : '',
                borderColor: isSelected ? theme?.secondary : theme?.tertiary,
                // The answer wears ink (theme primary), never the action colour.
                color: theme?.primary
            }}
            className="flex w-full cursor-pointer items-center justify-between rounded-xl border p-2 px-4 text-left"
            key={choice.id}
            onClick={() => onClick && onClick(choice.id || '')}
        >
            {choice.value ? choice.value : `Item ${index + 1}`} {isSelected && <Check className="h-5 w-5 shrink-0" />}
        </StyledChoiceButton>
    );
}
