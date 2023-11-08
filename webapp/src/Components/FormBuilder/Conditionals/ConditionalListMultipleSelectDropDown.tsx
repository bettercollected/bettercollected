import React, { Fragment, useState } from 'react';

import { Listbox } from '@headlessui/react';

import { ArrowDown } from '@app/components/icons/arrow-down';
import TickIcon from '@app/components/icons/tick-icon';

interface IConditionalListDropDown<T> {
    size?: string;
    className?: string;
    selectedState?: T;
    items: Array<T>;
    labelPicker?: (item: T) => string;
    setSelectedState: React.Dispatch<React.SetStateAction<T>>;
    multiple?: boolean;
}

const ConditionalListMultipleSelectDropDown = ({ size = 'large', className, selectedState, items, labelPicker, setSelectedState, multiple = false }: IConditionalListDropDown<any>) => {
    const displaySelectedValue = () => {
        if (multiple) {
            const displayValue = selectedState.map((state: any) => state.value);
            return displayValue.length > 0 ? displayValue.join(', ') : 'Select Fields';
        }
        return labelPicker ? labelPicker(selectedState) : selectedState?.value;
    };
    return (
        <Listbox value={selectedState} onChange={setSelectedState} multiple={multiple}>
            {({ open }) => {
                return (
                    <div className={`relative bg-white ${size === 'small' ? 'w-[160px]' : 'w-[280px]'} ${className}`}>
                        <Listbox.Button>
                            <div className={`flex justify-between border border-black-400 rounded p-2 text-sm font-normal text-black-800  ${open && 'border-black-900 '} ${size === 'small' ? 'w-[160px]' : 'w-[280px]'} `}>
                                <span className={'truncate'}>{displaySelectedValue()}</span>
                                <ArrowDown className={`${open ? 'rotate-180' : ''}`} />
                            </div>
                        </Listbox.Button>
                        <Listbox.Options>
                            <div className={'w-full mt-2 bg-white shadow-input py-2 gap-4 absolute z-20 rounded-lg'}>
                                {items.map((state: any, index: number) => (
                                    <Listbox.Option key={index} value={state} as={Fragment}>
                                        {({ active, selected }) => (
                                            <li className={`px-4 py-2 cursor-pointer truncate text-ellipsis text-base font-normal text-black-800 ${active ? 'bg-black-200 ' : 'bg-white text-black-800'}`}>
                                                <div className={'flex gap-2 items-center'}>
                                                    {multiple && <TickIcon className={`text-brand-500 h-5 w-5 ${selected ? 'visible' : 'invisible'}`} />} {labelPicker ? labelPicker(state) : state?.value}
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

export default ConditionalListMultipleSelectDropDown;
