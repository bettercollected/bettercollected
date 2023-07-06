import { ChangeEvent, useState } from 'react';

import { Divider, Select, SelectChangeEvent } from '@mui/material';
import MenuItem from '@mui/material/MenuItem';

import SelectDropdown from '@app/components/dropdown/select';
import { StandardFormQuestionDto } from '@app/models/dtos/form';

export default function DropdownField({ field }: { field: StandardFormQuestionDto }) {
    const [currentValue, setCurrentValue] = useState('');
    const onChange = (event: SelectChangeEvent<any>) => {
        setCurrentValue(event.target.value);
    };

    return (
        <Select value={currentValue} onChange={onChange} className="w-full mb-3 text-black-900 !bg-white">
            {(field?.properties?.choices || []).map((choice: any) => (
                <MenuItem key={choice.id} value={choice?.value}>
                    {choice.value}
                </MenuItem>
            ))}
        </Select>
    );
}
