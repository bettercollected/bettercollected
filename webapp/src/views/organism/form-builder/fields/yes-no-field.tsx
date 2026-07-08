import { RadioGroup } from '@headlessui/react';

import { StandardFormFieldDto } from '@app/models/dtos/form';
import { useFormState } from '@app/store/jotai/form';
import { styleTokens } from '@app/views/molecules/theme/theme-shared';

const YesNoField = ({ field, slide, disabled }: { field: StandardFormFieldDto; slide: StandardFormFieldDto; disabled: boolean }) => {
    const { theme } = useFormState();

    return (
        <>
            <RadioGroup className={'flex w-min flex-col gap-2'} value={field.value} onChange={() => {}}>
                {field &&
                    field.properties?.choices?.map((choice, index) => {
                        return (
                            <RadioGroup.Option value={choice.value} key={index}>
                                <div
                                    style={{
                                        borderColor: slide.properties?.theme?.tertiary || theme?.tertiary,
                                        // Ink, matching the responder rendering.
                                        color: slide.properties?.theme?.primary || theme?.primary,
                                        // Radius from the theme's style — the canvas previews what
                                        // responders get (hardcoded rounded-xl left the builder with
                                        // mixed radii next to the token-driven shared inputs).
                                        borderRadius: styleTokens((slide.properties?.theme || theme)?.style).inputRadius
                                    }}
                                    className={`flex w-[100px] justify-between border p-2 px-4`}
                                >
                                    {choice.value}
                                </div>
                            </RadioGroup.Option>
                        );
                    })}
            </RadioGroup>
        </>
    );
};

export default YesNoField;
