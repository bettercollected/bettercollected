import { Check } from 'lucide-react';
import styled from 'styled-components';

import { FormTheme } from '@app/constants/theme';
import { styleTokens } from '@app/views/molecules/theme/theme-shared';
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
    const tokens = styleTokens(theme?.style);
    const solid = tokens.solidSelection && isSelected;
    return (
        <StyledChoiceButton
            type="button"
            aria-pressed={isSelected}
            $theme={theme}
            style={{
                // Selection wears the action colour — a soft tint + border in the
                // quiet styles, a solid fill with white text in the studio style.
                // Colour is semantic here: it marks the responder's own answer.
                background: solid ? theme?.secondary : isSelected ? theme?.secondary + '1A' : '',
                borderColor: isSelected ? theme?.secondary : theme?.tertiary,
                color: solid ? '#ffffff' : theme?.primary,
                borderRadius: tokens.inputRadius
            }}
            className="flex w-full cursor-pointer items-center justify-between border p-2 px-4 text-left transition duration-150"
            key={choice.id}
            onClick={() => onClick && onClick(choice.id || '')}
        >
            {choice.value ? choice.value : `Item ${index + 1}`} {isSelected && <Check className="h-5 w-5 shrink-0" style={{ color: solid ? '#ffffff' : theme?.secondary }} />}
        </StyledChoiceButton>
    );
}
