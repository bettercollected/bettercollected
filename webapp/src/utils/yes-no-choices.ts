import { FieldChoice, StandardFormFieldDto } from '@app/models/dtos/form';

// A yes/no question always offers exactly Yes and No. The builder stores them
// as choices, but fields created elsewhere (seeded templates before they were
// fixed, older imports) can lack them — render the pair anyway, or the
// respondent sees a question with nothing to answer.
export const DEFAULT_YES_NO_CHOICES: FieldChoice[] = [
    { id: 'yes', value: 'Yes' },
    { id: 'no', value: 'No' }
];

export function yesNoChoices(field?: StandardFormFieldDto): FieldChoice[] {
    const stored = field?.properties?.choices ?? [];
    const values = stored.map((choice) => choice?.value);
    return values.includes('Yes') && values.includes('No') ? stored : DEFAULT_YES_NO_CHOICES;
}
