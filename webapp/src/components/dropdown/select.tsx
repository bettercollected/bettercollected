import React, { useState } from 'react';

import { Select, SelectProps } from '@mui/material';

interface ISelectDropdownProps extends SelectProps {
    value: string | number;
}

export default function SelectDropdown({ children, value, ...dropdownprops }: ISelectDropdownProps) {
    const [currentValue, setCurrentValue] = useState(value);
    const handleDropdownItem = (e: any) => {
        setCurrentValue(e.target.value);
    };
    return (
        <Select value={currentValue} onChange={handleDropdownItem} {...dropdownprops}>
            {children}
        </Select>
    );
}