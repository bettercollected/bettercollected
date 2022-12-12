import React, { useState } from 'react';

import { SandClock } from '../icons/sand-clock';
import TextInput from './text-input';

export default function DatePickerRenderer() {
    // const [startDate, setStartDate] = useState(new Date());
    return (
        <>
            <TextInput title="Date Picker">
                <SandClock className="pointer-events-none w-4 h-4 absolute text-gray-400 top-1/2 transform -translate-y-1/2 right-0 lg:right-1/2 mr-3" />
            </TextInput>
        </>
    );
}
