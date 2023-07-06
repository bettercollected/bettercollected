import Radio from '@mui/material/Radio';

import { StandardFormQuestionDto } from '@app/models/dtos/form';

export default function MultipleChoiceField({ field }: { field: StandardFormQuestionDto }) {
    return (
        <>
            {(field?.properties?.choices || []).map((choice: any) => (
                <div key={choice?.id} className="flex">
                    <Radio />
                    <div>{choice?.value}</div>
                </div>
            ))}
        </>
    );
}
