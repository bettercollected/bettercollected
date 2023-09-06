import React from 'react';

import { StandardFormDto } from '@app/models/dtos/form';
import { ConsentCategoryType, ConsentType } from '@app/models/enums/consentEnum';
import { selectConsentState } from '@app/store/consent/selectors';
import { useAppSelector } from '@app/store/hooks';

import ConsentBuilderField from './ConsentBuilderField';

interface ConsentBuilderFieldListProps {
    isPreview: boolean;
    category: ConsentCategoryType;
    form?: StandardFormDto;
}
export default function ConsentBuilderFieldList({ isPreview, category, form }: ConsentBuilderFieldListProps) {
    const consentState = useAppSelector(selectConsentState);

    if (isPreview) {
        return <div>{form?.consent.map((consent, idx) => consent?.category === category && <ConsentBuilderField key={consent.consentId} disabled={isPreview} className={`${idx === 0 && 'border-y'}`} consent={consent} />)}</div>;
    }

    return (
        <div>
            {[
                ...consentState.consents,
                {
                    consentId: 'consent_data_collection',
                    title: 'Data Collection',
                    description: 'We gather data from the responses you provide in our forms.',
                    type: ConsentType.Checkbox,
                    required: true,
                    category: ConsentCategoryType.PurposeOfTheForm
                }
            ].map((consent, idx) => consent?.category === category && <ConsentBuilderField key={consent.consentId} disabled={consent.consentId === 'consent_data_collection'} className={`${idx === 0 && 'border-y'}`} consent={consent} />)}
        </div>
    );
}
