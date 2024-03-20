import { MouseEvent } from 'react';

import { Check } from 'lucide-react';

import { FormTheme } from '@app/constants/theme';
import { FieldChoice } from '@app/models/dtos/form';

interface ChoiceProps {
    isSelected?: boolean;
    theme?: FormTheme;
    choice: FieldChoice;
    onClick?: (choiceId: string) => any;
}

export default function Choice({ isSelected, theme, choice, onClick }: ChoiceProps) {
    return (
        <div
            style={{
                background: isSelected ? theme?.tertiary : '',
                borderColor: theme?.tertiary
            }}
            className="flex cursor-pointer justify-between rounded-xl border p-2 px-4 hover:!border-black-900"
            key={choice.id}
            onClick={() => onClick && onClick(choice.id || '')}
        >
            {choice.value} {isSelected && <Check />}
        </div>
    );
}
