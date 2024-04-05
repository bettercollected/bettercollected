import { useState } from 'react';

import { useGetTemplatesQuery } from '@app/store/redux/templateApi';


export default function TemplateTab() {
    const [selectedTemplate, setSelectedTemplate] = useState();
    const { data: templates } = useGetTemplatesQuery({ v2: true });

    return (
        <>
            {selectedTemplate && <></>}
            {!selectedTemplate && <></>}
        </>
    );
}
