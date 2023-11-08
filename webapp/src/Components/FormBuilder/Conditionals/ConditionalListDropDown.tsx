import React, { Fragment, useState } from 'react';

import { Listbox } from '@headlessui/react';

import { ArrowDown } from '@app/components/icons/arrow-down';

interface IConditionalListDropDown<T> {
    size?: string;
    className?: string;
    defaultValue?: T;
    items: Array<T>;
    labelPicker?: (item: T) => string;
}

const ConditionalListDropDown = ({ size = 'large', className, defaultValue, items, labelPicker }: IConditionalListDropDown<any>) => {
    const [selectedState, setSelectedState] = useState(defaultValue);

    return (
        <Listbox value={selectedState} onChange={setSelectedState}>
            {({ open }) => {
                return (
                    <div className={`relative bg-white ${size === 'small' ? 'w-[160px]' : 'w-[280px]'} ${className}`}>
                        <Listbox.Button>
                            <div className={`flex justify-between border border-black-400 rounded p-2 text-sm font-normal text-black-800 ${open && 'border-black-900 '} ${size === 'small' ? 'w-[160px]' : 'w-[280px]'} `}>
                                {labelPicker ? labelPicker(selectedState) : selectedState?.value}
                                <ArrowDown className={`${open ? 'rotate-180' : ''}`} />
                            </div>
                        </Listbox.Button>
                        <Listbox.Options>
                            <div className={'w-full mt-2 bg-white shadow-input py-2 gap-4 absolute z-10 rounded-lg'}>
                                {items.map((state: any, index: number) => (
                                    <Listbox.Option key={index} value={state} as={Fragment}>
                                        {({ active, selected }) => (
                                            <li className={`px-4 py-2 cursor-pointer truncate text-ellipsis text-base font-normal text-black-800 ${active ? 'bg-black-200 ' : 'bg-white text-black-800'}`}>
                                                {' '}
                                                {labelPicker ? labelPicker(state) : state?.value}
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
