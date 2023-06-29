import React from 'react';

import { FormBuilderTagNames } from '@app/models/enums/formBuilder';

import FormBuilderInput from '../InputComponents/FormBuilderInput';

export default function FormBuilderBlockContent({ tag, position, reference }: any) {
    const renderBlockContent = () => {
        switch (tag) {
            case FormBuilderTagNames.INPUT_SHORT_TEXT:
                return <FormBuilderInput />;
            default:
                return null;
        }
    };

    return (
        <div className="w-full mb-4">
            <div data-position={position} data-tag={tag} ref={reference}>
                {renderBlockContent()}
            </div>
        </div>
    );
}
