import Checkbox from '@mui/material/Checkbox';

import { StandardFormQuestionDto } from '@app/models/dtos/form';

export default function CheckboxField({ field }: { field: StandardFormQuestionDto }) {
    return (
        <>
            {(field?.properties?.choices || []).map((choice: any) => (
                <div key={choice?.id} className="flex">
                    <Checkbox />
                    <div>{choice?.value}</div>
                </div>
            ))}
        </>
    );
}
