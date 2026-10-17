'use client';

import { v4 } from 'uuid';



import type { BuilderContext } from './index';

/** Choice mutations of the builder (multiple choice and dropdown options). */
export function choiceMutators(ctx: BuilderContext) {
    const { formFields, setFormFields } = ctx;

    const updateChoiceFieldValue = (fieldIndex: number, slideIndex: number, choiceId: string, choiceValue: string) => {
        const existingSlide = formFields[slideIndex];
        const slide = { ...existingSlide };
        slide.properties!.fields![fieldIndex]['properties'] = { ...(slide.properties!.fields![fieldIndex].properties || { fields: [] }) };
        slide.properties!.fields![fieldIndex]!.properties!.choices = slide.properties!.fields![fieldIndex]?.properties?.choices?.map((choice) => {
            if (choice.id === choiceId) {
                const existingChoice = { ...choice };
                existingChoice.value = choiceValue;
                return existingChoice;
            } else return choice;
        });
        const updatedSlides = [...formFields];
        setFormFields(updatedSlides, `choice:${slide.properties!.fields![fieldIndex].id}:${choiceId}`);
    };

    const addChoiceField = (fieldIndex: number, slideIndex: number) => {
        const choiceId = v4();
        const slide = formFields[slideIndex];
        slide.properties!.fields![fieldIndex]?.properties?.choices?.push({
            id: choiceId
        });
        const updatedSlides = [...formFields];
        setFormFields(updatedSlides);
    };

    const removeChoiceField = (fieldIndex: number, slideIndex: number, choiceId: string) => {
        const field = formFields[slideIndex].properties!.fields![fieldIndex];
        field.properties && (field.properties.choices = field?.properties?.choices?.filter((choice) => choice.id != choiceId));
        const updatedSlides = [...formFields];
        setFormFields(updatedSlides);
    };

    return { updateChoiceFieldValue, addChoiceField, removeChoiceField };
}
