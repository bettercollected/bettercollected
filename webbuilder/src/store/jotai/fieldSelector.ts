'use client';

import {atom, useAtom} from "jotai"
import {useActiveFieldComponent, useActiveSlideComponent} from "@app/store/jotai/activeBuilderComponent";

import { FormField } from '@app/models/dtos/form';

const initialFieldsAtom = atom<FormField[]>([]);

export default function useFieldSelectorAtom() {
    const [formFields, setFormFields] = useAtom(initialFieldsAtom);

    const {activeSlideComponent} = useActiveSlideComponent()
    const {activeFieldComponent} = useActiveFieldComponent()

    const addSlide = (field: FormField) => {
        setFormFields([...formFields, field]);
    };


    const getActiveSlide = () => {
        if (activeSlideComponent?.index !== undefined)
            return formFields[activeSlideComponent!.index];
        return;
    };


    const activeSlide = getActiveSlide()

    const getActiveField = () => {
        if (activeFieldComponent?.index !== undefined)
            return activeSlide?.properties?.fields![activeFieldComponent.index]
        return
    }
    const activeField = getActiveField()

    const addField = (slideField: FormField, slideIndex: number) => {
        const slide = formFields[slideIndex];
        slide.properties?.fields!.push(slideField);
        const updatedSlides = [...formFields];
        setFormFields(updatedSlides);
    };

    const updateTitle = (fieldIndex: number, slideIndex: number, titleText: string) => {
        const slide = formFields[slideIndex];
        slide.properties!.fields![fieldIndex].title = titleText;
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

    return {
        formFields,
        addField,
        addSlide,
        updateTitle,
        updateFieldPlaceholder,
        updateChoiceFieldValue,
        addChoiceField,
        updateFieldRequired,
        updateFieldValidation,
        updateShowQuestionNumbers,
        activeSlide,
        activeField
    }
}
