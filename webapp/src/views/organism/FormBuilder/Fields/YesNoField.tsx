import { RadioGroup } from '@headlessui/react';

import { StandardFormFieldDto } from '@app/models/dtos/form';
import { useFormState } from '@app/store/jotai/form';

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
                                        color: theme?.secondary
                                    }}
                                    className={`flex justify-between rounded-xl border p-2 px-4`}
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
