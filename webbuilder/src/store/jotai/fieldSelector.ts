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
        const newSlides = formFields.splice(slideIndex, 1, slide)
        setFormFields(newSlides)
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


    return {formFields, addField, addSlide, updateTitle, updateFieldPlaceholder,updateChoiceFieldValue,addChoiceField}
}
