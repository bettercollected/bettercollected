import React, { Fragment, useEffect, useState } from 'react';

import { Listbox } from '@headlessui/react';

import { ArrowDown } from '@app/components/icons/arrow-down';
import TickIcon from '@app/components/icons/tick-icon';
import { getIconForFieldType } from '@app/utils/conditionalUtils';

interface IConditionalListDropDown<T> {
    size?: string;
    className?: string;
    value?: T;
    defaultValue?: T;
    items?: Array<T>;
    labelPicker?: (item: T) => string;
    onChange?: (item: T) => void;
    multiple?: boolean;
    showIcons?: boolean;
}

const ConditionalListDropDown = ({ size = 'large', className, defaultValue, value, items = [], labelPicker, onChange, multiple = false, showIcons }: IConditionalListDropDown<any>) => {
    const [selectedState, setSelectedState] = useState(value || defaultValue || (multiple ? [] : null));

    const handleChange = (item: any) => {
        onChange && onChange(item);
        // setSelectedState(item);
    };
    const displaySelectedValue = () => {
        if (multiple) {
            const displayValue = selectedState?.map((state: any) => (labelPicker ? labelPicker(state) : state?.value));
            return displayValue.length > 0 ? displayValue.join(', ') : 'Select Fields';
        }
        return labelPicker ? labelPicker(selectedState) : selectedState?.value;
    };

    useEffect(() => {
        setSelectedState(value);
    }, [value]);

    return (
        <Listbox value={selectedState} onChange={handleChange} multiple={multiple}>
            {({ open }) => {
                return (
                    <div className={`relative bg-white w-full ${size === 'small' ? 'basis-1/3 ' : 'md:w-[370px]'} ${className || ''}`}>
                        <Listbox.Button className="w-full">
                            <div className={`flex justify-between border border-black-400 rounded p-2 text-sm font-normal text-black-800 ${open && 'border-black-900 '}`}>
                                <div className={'w-full truncate text-start'}>{displaySelectedValue()}</div>
                                <ArrowDown className={`${open ? 'rotate-180' : ''}`} />
                            </div>
                        </Listbox.Button>
                        <Listbox.Options>
                            <div className={'w-full mt-2 bg-white shadow-input py-2 gap-4 absolute z-[100] rounded-lg'}>
                                {items.map((item: any, index: number) => (
                                    <Listbox.Option key={index} value={item} as={Fragment}>
                                        {({ active, selected }) => (
                                            <li className={`px-2 md:px-4 py-2 cursor-pointer truncate text-base font-normal text-black-800 ${active ? 'bg-black-200 ' : 'bg-white text-black-800'}`}>
                                                <div className={'flex gap-1 sm:gap-2 items-center'}>
                                                    {multiple && (
                                                        <div className={`text-brand-500 h-5 min-w-1 md:min-w-3 w-5 ${selected ? 'visible' : 'invisible'}`}>
                                                            <TickIcon />
                                                        </div>
                                                    )}
                                                    {showIcons && <span className="mr-2">{getIconForFieldType(item.fieldType)}</span>}
                                                    <span>{labelPicker ? labelPicker(item) : item?.value}</span>
                                                </div>
                                            </li>
                                        )}
                                    </Listbox.Option>
                                ))}
                            </div>
                        </Listbox.Options>
                    </div>
                );
            }}
        </Listbox>
    );
};

export default ConditionalListDropDown;
