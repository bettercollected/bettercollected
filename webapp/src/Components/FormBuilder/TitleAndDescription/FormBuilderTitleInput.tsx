import React from 'react';

export default function FormBuilderTitleInput({ title, handleFormTitleChange }: any) {
    return <input value={title} type="text" onChange={handleFormTitleChange} placeholder="Form title" />;
}
