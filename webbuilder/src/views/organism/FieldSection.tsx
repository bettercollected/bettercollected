'use client';

import React from 'react';

import useFieldSelectorAtom from "@app/store/jotai/fieldSelector";
import TextField from '@mui/material/TextField';
import { FieldTypes, FormField } from "@app/models/dtos/form";
import { FolderUploadIcon } from '../atoms/Icons/FolderUploadIcon';
import { useActiveFieldComponent } from "@app/store/jotai/activeBuilderComponent";
import cn from "classnames";
import { RadioGroup } from '@headlessui/react'
import { ArrowDown } from '../atoms/Icons/ArrowDown';
import { Button } from '@app/shadcn/components/ui/button';
import { PlusIcon } from '../atoms/Icons/Plus';

const FieldSection = ({ slide, disabled = false }: { slide: FormField, disabled?: boolean }) => {
    // const {fields} = useFieldSelectorAtom();
    const slideFields = slide.properties?.fields

    const { setActiveFieldComponent } = useActiveFieldComponent()

    function renderField(field: FormField) {
        switch (field.type) {
            case (FieldTypes.EMAIL):
            case (FieldTypes.NUMBER):
            case (FieldTypes.SHORT_TEXT):
            case (FieldTypes.LINK):
            case (FieldTypes.PHONE_NUMBER):
                return <InputField field={field} slide={slide} disabled={disabled} />
            case (FieldTypes.FILE_UPLOAD):
                return <FileUpload field={field} slide={slide} />
            case (FieldTypes.YES_NO):
                return <YesNoField field={field} slide={slide} />
            case (FieldTypes.DROP_DOWN):
            case (FieldTypes.MULTIPLE_CHOICE):
                return <DropDownField field={field} slide={slide} />;
        }
    }

    return <div className={cn("h-min w-full aspect-video overflow-y-auto bg-white", disabled && "pointer-events-none")}>
        <div className={'flex flex-col gap-20 px-20 py-10 justify-center'}>
            {Array.isArray(slideFields) && slideFields.length ? slideFields.map((field, index) => {
                return <div key={index} tabIndex={0} className="focus-within:ring-1" onFocus={() => {
                    setActiveFieldComponent({ id: field.id, index: index })
                }} onBlur={() => {
                    setActiveFieldComponent(null)
                }}>
                    {renderField(field)}
                </div>
            }) : <></>}
        </div>
    </div>
}
export default FieldSection

const FileUpload = ({ field, slide }: { field: FormField, slide: FormField }) => {
    const { updateTitle } = useFieldSelectorAtom();
    const handleFileInputChange = (event: any) => {
        const file = event.target.files[0];
        if (file.size > 26214400) alert('Size greater than 25MB.')
    };
    return <div className={'flex flex-col items-start'}>
        <input id={`input-${field.id}`} type="text" className={'px-0 -left-1 border-0 text-2xl'} value={field.title}
            onChange={(e: any) => updateTitle(field.index, slide.index, e.target.value)} />
        <label htmlFor="form-builder-file-upload"
            className={'h-[200px] w-[500px] cursor-pointer border-2 border-brand-500 rounded-2xl border-dotted flex flex-col gap-2 justify-center items-center'}>
            <FolderUploadIcon />
            <div className={'flex flex-col gap-1 items-center'}><span className={'text-base font-semibold'}>Choose your file or drag file</span>
                <span className={'text-[12px]'}>Max size limit: 25 MB</span></div>
        </label>
        <input type="file" id="form-builder-file-upload" className={'invisible'} onChange={handleFileInputChange} />
    </div>
}

const InputField = ({ field, slide, disabled }: { field: FormField, slide: FormField, disabled: boolean }) => {
    const { updateTitle, updateFieldPlaceholder } = useFieldSelectorAtom();

    return <div className={'flex flex-col items-start'}>
        <input id={`input-${disabled ? `${slide.id}${field.id}` : field.id}`} type="text" className={'px-0 -left-1 border-0 text-2xl'} value={field.title}
            onChange={(e: any) => updateTitle(field.index, slide.index, e.target.value)} />
        <TextField sx={{
            '& .MuiOutlinedInput-root': {
                '& fieldset': {
                    border: 'none',
                    borderBottom: '1px solid #407270',
                },
                '&:hover fieldset': {
                    border: 'none',
                    borderBottom: '1px solid #407270',
                },
                '&.Mui-focused fieldset': {
                    border: 'none',
                    borderBottom: '1px solid #407270',
                },
                '& .MuiInputBase-input': {
                    color: '#407270',
                    fontSize: 24,
                    paddingLeft: 0
                },
            },
        }} type={field.type} value={field.properties?.placeholder}
            onChange={(e: any) => updateFieldPlaceholder(field.index, slide.index, e.target.value)}
            className={'w-2/3 border-0 border-b-[1px] border-cyan-500'} />
    </div>
}

const YesNoField = ({ field, slide }: { field: FormField, slide: FormField }) => {
    const { updateTitle } = useFieldSelectorAtom();
    return <div className={'flex flex-col items-start'}>
        <input id={`input-${field.id}`} type="text" className={'px-0 -left-1 border-0 text-2xl'} value={field.title}
            onChange={(e: any) => updateTitle(field.index, slide.index, e.target.value)} />
        <RadioGroup className={'flex flex-col gap-2 w-1/3'} value={field.value} onChange={() => {
        }}>
            {field && field.properties?.choices?.map((choice, index) => {
                return <RadioGroup.Option value={choice.value} key={index}>
                    <div
                        className={`rounded-xl border border-cyan-500 p-2 px-4 flex justify-between`}>{choice.value}
                    </div>
                </RadioGroup.Option>
            })}
        </RadioGroup>
    </div>
}

const DropDownField = ({ field, slide }: { field: FormField, slide: FormField }) => {
    const { updateTitle, updateChoiceFieldValue, addChoiceField } = useFieldSelectorAtom();
    return <div className={'flex flex-col items-start gap-4'}>
        <input id={`input-${field.id}`} type="text" className={'px-0 -left-1 border-0 text-2xl'} value={field.title}
            onChange={(e: any) => updateTitle(field.index, slide.index, e.target.value)} />
        {field.type === FieldTypes.DROP_DOWN &&
            <div className='flex justify-between w-1/3 py-2 text-2xl text-cyan-500 items-center border-0 border-cyan-500 border-b-[1px]'><h1>Select an option</h1> <ArrowDown className='stroke-2' /> </div>
        }
        <div className={'flex flex-col gap-2 w-1/3'}>
            {field && field.properties?.choices?.map((choice, index) => {
                return <>
                    <input type='text' value={choice.value}
                        onChange={(e: any) => updateChoiceFieldValue(field.index, slide.index, choice.id, e.target.value)}
                        className={`rounded-xl border border-cyan-500 p-2 px-4 flex justify-between`} />
                </>
            })}
        </div>
        <Button onClick={() => addChoiceField(field.index, slide.index)} variant={'ghost'} className='text-lg font-semibold' icon={<PlusIcon className='h-4 w-4' />}>Add Option</Button>
    </div>
}


