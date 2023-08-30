import React, { Fragment, forwardRef, useEffect, useState } from 'react';

import AppButton from '@Components/Common/Input/Button/AppButton';
import { Combobox, Transition } from '@headlessui/react';
import cn from 'classnames';

import { AddIcon } from '@app/components/icons/add';
import { ArrowDown } from '@app/components/icons/arrow-down';
import { DropdownCloseIcon } from '@app/components/icons/dropdown-close';
import { ConsentPurposeModalMode } from '@app/components/modal-views/modals/consent-purpose-modal-view';
import { OnlyClassNameInterface } from '@app/models/interfaces';

interface AutoCompleteInputProps extends OnlyClassNameInterface {
    dropdownTitle?: string;
    title?: string;
    placeholder?: string;
    options: string[];
    required?: boolean;
    onSelect?: (selection: string, mode?: ConsentPurposeModalMode) => void;
}

const AutoCompleteInput = forwardRef<HTMLDivElement, AutoCompleteInputProps>(({ title, dropdownTitle, placeholder = '', required = false, onSelect, options, className }, ref) => {
    const [selected, setSelected] = useState('');
    const [query, setQuery] = useState('');

    const filteredoptions = query === '' ? options : options.filter((option) => option.toLowerCase().replace(/\s+/g, '').includes(query.toLowerCase().replace(/\s+/g, '')));

    useEffect(() => {
        if (selected.length !== 0) {
            onSelect && onSelect(selected);
            setSelected('');
        }
    }, [selected]);
    return (
        <div className={cn('w-full', className)} ref={ref}>
            <Combobox value={selected} onChange={setSelected}>
                {({ open }) => (
                    <div className="relative mt-1">
                        {title && (
                            <div className="h5-new mb-3">
                                {title} {required && <span className="text-pink ml-2">*</span>}
                            </div>
                        )}
                        <div className="relative w-full cursor-default border-none overflow-hidden rounded-md  bg-white text-left group">
                            <Combobox.Input
                                placeholder={placeholder}
                                className="w-full rounded-md border border-black-300 focus:border-blue-500 p-3 text-base leading-6 text-gray-900 placeholder:text-black-400 focus:ring-0"
                                displayValue={(option: string) => (option ? option : '')}
                                onChange={(event) => setQuery(event.target.value)}
                            />
                            <Combobox.Button className="absolute inset-y-0 right-0 flex items-center pr-2">
                                <ArrowDown aria-hidden="true" className={`${open && 'rotate-180'} transition delay-150 ease-in-out`} />
                            </Combobox.Button>
                        </div>
                        <Transition as={Fragment} leave="transition ease-in duration-100" leaveFrom="opacity-100" leaveTo="opacity-0" afterLeave={() => setQuery('')}>
                            <Combobox.Options className="absolute mt-3 max-h-[321px] w-full leading-6 rounded-lg bg-white shadow-lg shadow-dropdown-shadow border border-blue-200 z-50">
                                {dropdownTitle && (
                                    <div className="py-4 px-6 leading-5 flex justify-between items-center border-b border-black-200">
                                        <div className="p2 !text-black-800">{dropdownTitle}</div> <DropdownCloseIcon />
                                    </div>
                                )}
                                <div className="py-4">
                                    <div className="dropdown-scrollbar px-6 overflow-auto max-h-[150px] space-y-1">
                                        {filteredoptions.length === 0 && query !== '' ? (
                                            <div className="relative cursor-default select-none py-2 px-4 text-gray-700">Nothing found.</div>
                                        ) : (
                                            filteredoptions.map((option, idx) => (
                                                <Combobox.Option key={idx} className={({ active }) => `relative p1 !text-black-800 rounded-sm cursor-default select-none py-2 px-4 ${active ? 'bg-black-200' : 'text-black-800'}`} value={option}>
                                                    {({ selected, active }) => (
                                                        <>
                                                            <span className={`block truncate `}>{option}</span>
                                                        </>
                                                    )}
                                                </Combobox.Option>
                                            ))
                                        )}
                                    </div>
                                    <div className="px-6">
                                        <AppButton
                                            className="flex space-x-2 items-center justify-center !w-full mt-4"
                                            onClick={(event: any) => {
                                                event.preventDefault();
                                                onSelect && onSelect('', 'create');
                                            }}
                                        >
                                            <AddIcon />
                                            <span>Create New</span>
                                        </AppButton>
                                    </div>
                                </div>
                            </Combobox.Options>
                        </Transition>
                    </div>
                )}
            </Combobox>
        </div>
    );
});

AutoCompleteInput.displayName = 'ConsentAutoCompleteInput';
export default AutoCompleteInput;
