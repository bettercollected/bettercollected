'use client';

import { atom, useAtom } from 'jotai';
import { v4 } from 'uuid';

import { FormField } from '@app/models/dtos/form';
import {
    useActiveFieldComponent,
    useActiveSlideComponent
} from '@app/store/jotai/activeBuilderComponent';
import { reorder } from '@app/utils/arrayUtils';

const initialFieldsAtom = atom<FormField[]>([]);

export default function useFormFieldsAtom() {
    const [formFields, setFormFields] = useAtom(initialFieldsAtom);

    const { activeSlideComponent } = useActiveSlideComponent();
    const { activeFieldComponent } = useActiveFieldComponent();

    const addSlide = (field: FormField) => {
        setFormFields([...formFields, field]);
    };

    const getActiveSlide = () => {
        if (activeSlideComponent?.index !== undefined)
            return formFields[activeSlideComponent!.index];
        return;
    };

    const activeSlide = getActiveSlide();

    const getActiveField = () => {
        if (activeFieldComponent?.index !== undefined)
            return activeSlide?.properties?.fields![activeFieldComponent.index];
        return;
    };
    const activeField = getActiveField();

    const addField = (slideField: FormField, slideIndex: number) => {
        const slide = formFields[slideIndex];
        slide.properties?.fields!.push(slideField);
        const updatedSlides = [...formFields];
        setFormFields(updatedSlides);
    };

    const updateTitle = (fieldIndex: number, slideIndex: number, titleText: string) => {
        const slide = formFields[slideIndex];
        slide.properties!.fields![fieldIndex] = {
            ...(slide.properties!.fields![fieldIndex] || {}),
            title: titleText
        };
        const updatedSlides = [...formFields];
        setFormFields(updatedSlides);
    };

    const updateDescription = (
        fieldIndex: number,
        slideIndex: number,
        description: string | undefined
    ) => {
        const slide = formFields[slideIndex];
        slide.properties!.fields![fieldIndex].description = description;
        const updatedSlides = [...formFields];
        setFormFields(updatedSlides);
    };

    const updateFieldPlaceholder = (
        fieldIndex: number,
        slideIndex: number,
        placeholderText: string
    ) => {
        const slide = formFields[slideIndex];
        slide.properties!.fields![fieldIndex]['properties'] = slide.properties!.fields![
            fieldIndex
        ].properties || { fields: [] };
        slide.properties!.fields![fieldIndex]!.properties!.placeholder =
            placeholderText;
        const updatedSlides = [...formFields];
        setFormFields(updatedSlides);
    };

    const updateChoiceFieldValue = (
        fieldIndex: number,
        slideIndex: number,
        choiceId: string,
        choiceValue: string
    ) => {
        const slide = formFields[slideIndex];
        slide.properties!.fields![fieldIndex]!.properties!.choices =
            slide.properties!.fields![fieldIndex]?.properties?.choices?.map(
                (choice) => {
                    if (choice.id === choiceId) {
                        choice.value = choiceValue;
                        return choice;
                    } else return choice;
                }
            );
        const updatedSlides = [...formFields];
        setFormFields(updatedSlides);
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

    const updateFieldRequired = (
        fieldIndex: number,
        slideIndex: number,
        required: boolean
    ) => {
        formFields[slideIndex].properties!.fields![fieldIndex].validations = {
            ...formFields[slideIndex].properties!.fields![fieldIndex].validations,
            required: required
        };
        setFormFields([...formFields]);
    };

    const updateFieldValidation = (
        fieldIndex: number,
        slideIndex: number,
        validation: any
    ) => {
        formFields[slideIndex].properties!.fields![fieldIndex].validations = {
            ...formFields[slideIndex].properties!.fields![fieldIndex].validations,
            ...validation
        };
        setFormFields([...formFields]);
    };

    const updateShowQuestionNumbers = (slideIndex: number, show: boolean) => {
        formFields![slideIndex]!.properties = {
            ...(formFields[slideIndex].properties || {}),
            showQuestionNumbers: show
        };
        setFormFields([...formFields]);
    };

    const updateSlideTheme = (color: {
        title: string;
        primary: string;
        secondary: string;
        tertiary: string;
        accent: string;
    }) => {
        formFields[activeSlide?.index || 0].properties!.theme = {
            title: color.title,
            primary: color.primary,
            secondary: color.secondary,
            tertiary: color.tertiary,
            accent: color.accent
        };
        setFormFields([...formFields]);
    };

    const moveFieldInASlide = (
        slideIndex: number,
        sourceIndex: number,
        destinationIndex: number
    ) => {
        formFields![slideIndex]!.properties!.fields = reorder(
            formFields![slideIndex]!.properties!.fields!,
            sourceIndex,
            destinationIndex
        );
        setFormFields([...formFields]);
    };

    const updateFieldProperty = (
        fieldIndex: number,
        slideIndex: number,
        property: string,
        value: any
    ) => {
        formFields![slideIndex]!.properties!.fields![fieldIndex].properties = {
            ...(formFields![slideIndex]!.properties!.fields![fieldIndex].properties ||
                {}),
            [property]: value
        };
        setFormFields([...formFields]);
    };

    const deleteField = (slideIndex: number, fieldIndex: number) => {
        formFields![slideIndex]!.properties!.fields!.splice(fieldIndex, 1);
        setFormFields([...formFields]);
    };

    const resetFields = () => {
        setFormFields([]);
    };

    return {
        formFields,
        setFormFields,
        addField,
        addSlide,
        updateTitle,
        updateDescription,
        updateFieldPlaceholder,
        updateChoiceFieldValue,
        addChoiceField,
        updateFieldRequired,
        updateFieldValidation,
        updateFieldProperty,
        updateShowQuestionNumbers,
        updateSlideTheme,
        moveFieldInASlide,
        activeSlide,
        activeField,
        deleteField,
        resetFields
    };
}
