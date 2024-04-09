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

const StyledDiv = styled.div<{ $theme: any }>(({ $theme }) => {
    const secondaryColor = $theme?.secondary;
    return {
        '&:hover': {
            borderColor: secondaryColor + '!important'
        }
    };
});

export default function Choice({
    isSelected,
    theme,
    index,
    choice,
    onClick
}: ChoiceProps) {
    return (
        <StyledDiv
            $theme={theme}
            style={{
                background: isSelected ? theme?.tertiary : '',
                borderColor: theme?.tertiary
            }}
            className="flex cursor-pointer justify-between rounded-xl border p-2 px-4 "
            key={choice.id}
            onClick={() => onClick && onClick(choice.id || '')}
        >
            {choice.value ? choice.value : `Item ${index + 1}`}{' '}
            {isSelected && <Check />}
        </StyledDiv>
    );
}
