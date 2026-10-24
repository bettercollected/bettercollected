import { StandardFormFieldDto } from '@app/models/dtos/form';
import { useFormState } from '@app/store/jotai/form';
import { yesNoChoices } from '@app/utils/yes-no-choices';
import { ChoiceContent, choiceRowStyle, initialKeys, showsOptionKeys } from '@app/views/atoms/choice';
import { styleTokens } from '@app/views/molecules/theme/theme-shared';

/**
 * The canvas's Yes/No: the respondent's option rows (atoms/choice.tsx), drawn
 * unselected and inert, so the canvas previews what respondents get.
 */
const YesNoField = ({ field, slide }: { field: StandardFormFieldDto; slide: StandardFormFieldDto; disabled: boolean }) => {
    const { theme } = useFormState();
    const rowTheme = slide.properties?.theme?.secondary ? { ...theme, ...slide.properties.theme } : theme;
    const ruled = styleTokens(rowTheme?.style).ruledChoices;
    const choices = yesNoChoices(field);
    // The respondent's key letters, on a theme that shows them.
    const keys = showsOptionKeys(rowTheme) ? initialKeys(choices.map((choice) => choice.value ?? '')) : [];

    return (
        <div className={ruled ? 'flex w-full flex-col' : 'flex w-full max-w-xs flex-col gap-2'} aria-hidden="true">
            {field &&
                choices.map((choice, index) => {
                    const row = choiceRowStyle(rowTheme, false);
                    return (
                        <div key={index} className={row.className} style={row.style}>
                            <ChoiceContent kind="radio" theme={rowTheme} solid={row.solid} keyHint={keys[index]}>
                                {choice.value}
                            </ChoiceContent>
                        </div>
                    );
                })}
        </div>
    );
};

export default YesNoField;
