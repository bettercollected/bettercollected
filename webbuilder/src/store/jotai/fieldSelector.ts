'use client';

import {atom, useAtom} from "jotai"
import {FormField} from "@app/models/dtos/form";
import { v4 } from "uuid";

const initialFieldsAtom = atom<FormField[]>([])

export default function useFieldSelectorAtom() {
    const [formFields, setFormFields] = useAtom(initialFieldsAtom);

    const addSlide = (field: FormField) => {
        setFormFields([...formFields, field])
    }

    const addField = (slideField: FormField, slideIndex: number) => {
        const slide = formFields[slideIndex]
        slide.properties?.fields.push(slideField)
        const updatedSlides = [...formFields]
        setFormFields(updatedSlides)
    }

    const updateTitle = (fieldIndex:number,slideIndex:number, titleText: string) => {
        const slide = formFields[slideIndex]
        slide.properties!.fields[fieldIndex].title = titleText
        const updatedSlides = [...formFields]
        setFormFields(updatedSlides)
    }
    const updateFieldPlaceholder = (fieldIndex: number,slideIndex:number, placeholderText: string) => {
        const slide = formFields[slideIndex];
        slide.properties!.fields[fieldIndex]['properties'] = slide.properties!.fields[fieldIndex].properties || {fields:[]};
        slide.properties!.fields[fieldIndex]!.properties!.placeholder = placeholderText;
        const updatedSlides = [...formFields];
        setFormFields(updatedSlides);
    }

    const updateChoiceFieldValue = (fieldIndex:number,slideIndex:number,choiceId:string,choiceValue:string)=>{
        const slide = formFields[slideIndex];
        const updatedChoices = slide.properties!.fields[fieldIndex]?.properties?.choices?.map((choice)=>{
            if (choice.id === choiceId){
                choice.value = choiceValue
                return choice
            }
            else return choice
        })
        slide.properties!.fields[fieldIndex]!.properties!.choices = updatedChoices
        const updatedSlides = [...formFields];
        setFormFields(updatedSlides);
    }

    const addChoiceField = (fieldIndex:number,slideIndex:number)=>{
        const choiceId = v4();
        const slide = formFields[slideIndex];
        slide.properties!.fields[fieldIndex]?.properties?.choices?.push({id:choiceId})
        const updatedSlides = [...formFields];
        setFormFields(updatedSlides)
    }

    const updateFieldRequired = (fieldIndex: number, slideIndex: number, required: boolean) => {
        formFields[slideIndex].properties!.fields[fieldIndex].validations = {
            ...formFields[slideIndex].properties!.fields[fieldIndex].validations,
            required: required
        }
        setFormFields([...formFields])
    }

    const updateFieldValidation = (fieldIndex: number, slideIndex: number, validation: any) => {
        formFields[slideIndex].properties!.fields[fieldIndex].validations = {
            ...formFields[slideIndex].properties!.fields[fieldIndex].validations,
            ...validation
        }
        setFormFields([...formFields])
    }

    return {formFields, addField, addSlide, updateTitle, updateFieldPlaceholder,updateChoiceFieldValue,addChoiceField}
}
