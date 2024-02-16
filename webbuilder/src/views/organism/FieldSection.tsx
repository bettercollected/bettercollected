'use client';

import React from 'react';

import useFieldSelectorAtom from "@app/store/jotai/fieldSelector";
import TextField from '@mui/material/TextField';
import {FieldTypes, FormField} from "@app/models/dtos/form";
import UploadIcon from "@app/views/atoms/Icons/UploadIcon";
import {FolderUploadIcon} from '../atoms/Icons/FolderUploadIcon';

const FieldSection = ({slide}: { slide: FormField }) => {
    // const {fields} = useFieldSelectorAtom();
    const slideFields = slide.properties?.fields

    function renderField(field: FormField) {
        switch (field.type) {
            case (FieldTypes.EMAIL):
            case (FieldTypes.NUMBER):
            case (FieldTypes.SHORT_TEXT):
                return <InputField field={field}/>
            case (FieldTypes.FILE_UPLOAD):
                return <FileUpload field={field}/>

        }
    }

    return <div className=" h-min w-full aspect-video bg-white">
        <div className={'flex flex-col gap-20 px-20 py-10 overflow-y-scroll h-full justify-center'}>
            {Array.isArray(slideFields) && slideFields.length ? slideFields.map((field, index) => {
                return <div key={index}>
                    {renderField(field)}
                </div>
            }) : <></>}
        </div>
    </div>
}
export default FieldSection

const FileUpload = ({field}: { field: FormField }) => {
    const {updateTitle} = useFieldSelectorAtom();
    const handleFileInputChange = (event: any) => {
        const file = event.target.files[0];
        if (file.size > 26214400) alert('Size greater than 25MB.')
    };
    return <div className={'flex flex-col items-start'}>
        <input id={`input-${field.id}`} type="text" className={'px-0 -left-1 border-0 text-2xl'} value={field.title}
               onChange={(e: any) => updateTitle(field.id, e.target.value)}/>
        <label htmlFor="form-builder-file-upload"
               className={'h-[200px] w-[500px] cursor-pointer border-2 border-brand-500 rounded-2xl border-dotted flex flex-col gap-2 justify-center items-center'}>
            <FolderUploadIcon/>
            <div className={'flex flex-col gap-1 items-center'}><span className={'text-base font-semibold'}>Choose your file or drag file</span>
                <span className={'text-[12px]'}>Max size limit: 25 MB</span></div>
        </label>
        <input type="file" id="form-builder-file-upload" className={'hidden'} onChange={handleFileInputChange}/>
    </div>
}

const InputField = ({field}: { field: FormField }) => {
    const {updateTitle, updateFieldPlaceholder} = useFieldSelectorAtom();

    return <div className={'flex flex-col items-start'}>
        <input id={`input-${field.id}`} type="text" className={'px-0 -left-1 border-0 text-2xl'} value={field.title}
               onChange={(e: any) => updateTitle(field.id, e.target.value)}/>
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
                   onChange={(e: any) => updateFieldPlaceholder(field.index, e.target.value)}
                   className={'w-2/3 border-0 border-b-[1px] border-cyan-500'}/>
    </div>
}
