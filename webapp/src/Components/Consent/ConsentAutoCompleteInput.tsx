import React, { Fragment, forwardRef, useRef, useState } from 'react';

import AppButton from '@Components/Common/Input/Button/AppButton';
import { Combobox, Transition } from '@headlessui/react';
import cn from 'classnames';

import { AddIcon } from '@app/components/icons/add';
import { ArrowDown } from '@app/components/icons/arrow-down';
import { DropdownCloseIcon } from '@app/components/icons/dropdown-close';
import { ConsentPurposeModalMode } from '@app/components/modal-views/modals/consent-purpose-modal-view';
import { ConsentCategoryType, ConsentType } from '@app/models/enums/consentEnum';
import { OnlyClassNameInterface } from '@app/models/interfaces';
import { IConsentOption } from '@app/models/types/consentTypes';


interface ConsentAutoCompleteInputProps extends OnlyClassNameInterface {
    dropdownTitle?: string;
    title?: string;
    placeholder?: string;
    options: IConsentOption[];
    required?: boolean;
    showCreateNewOptionButton?: boolean;
    onSelect?: (selection: IConsentOption, mode?: ConsentPurposeModalMode) => void;
}

const ConsentAutoCompleteInput = forwardRef<HTMLDivElement, ConsentAutoCompleteInputProps>(({ title, dropdownTitle, placeholder = '', required = false, onSelect, options, className, showCreateNewOptionButton = false }, ref) => {
    const [isOptionsVisible, setOptionsVisible] = useState(true);
    const [query, setQuery] = useState('');

    const filteredOptions = query === '' ? options : options.filter((option) => option.title?.toLowerCase().replace(/\s+/g, '').includes(query.toLowerCase().replace(/\s+/g, '')));
    const inputRef = useRef<HTMLInputElement>(null);
    const handleInputChange = (event: any) => {
        const inputValue = event.target.value;
        setQuery(inputValue);
        setOptionsVisible(true);
    };

    const handleCreateNew = (event: any) => {
        event.preventDefault();
        if (inputRef.current) {
            inputRef.current.blur();
        }
        onSelect && onSelect({ type: ConsentType.Checkbox, category: ConsentCategoryType.PurposeOfTheForm }, 'create');
        setOptionsVisible(false);
    };

    return (
        <div className={cn('w-full', className)} ref={ref}>
            <Combobox
                value={null}
                onChange={(selected: IConsentOption) => {
                    if (inputRef.current) {
                        inputRef.current.blur();
                    }
                    onSelect && onSelect(selected);
                }}
            >
                {({ open }) => {
                    return (
                        <div className="relative mt-1">
                            {title && (
                                <div className="h4-new mb-3">
                                    {title} {required && <span className="text-pink ml-2">*</span>}
                                </div>
                            )}
                            <div className="relative w-full cursor-default border-none overflow-hidden rounded-md  bg-white text-left group">
                                <Combobox.Input
                                    ref={inputRef}
                                    placeholder={placeholder}
                                    className="w-full rounded-md border border-black-300 focus:border-blue-500 p-3 sm:text-base text-sm leading-6 text-gray-900 placeholder:text-black-400 focus:ring-0"
                                    displayValue={(option: string) => (option ? option : '')}
                                    onChange={handleInputChange}
                                />
                                <Combobox.Button
                                    className="absolute inset-y-0 right-0 flex items-center pr-2"
                                    onClick={() => {
                                        setOptionsVisible(true);
                                    }}
                                >
                                    <ArrowDown aria-hidden="true" className={`${isOptionsVisible && open && 'rotate-180'} transition delay-150 ease-in-out`} />
                                </Combobox.Button>
                            </div>
                            <Transition show={isOptionsVisible && open} as={Fragment} leave="transition ease-in duration-100" leaveFrom="opacity-100" leaveTo="opacity-0" afterLeave={() => setQuery('')}>
                                <Combobox.Options className="absolute mt-3 max-h-[321px] w-full leading-6 rounded-lg bg-white shadow-lg shadow-dropdown-shadow border border-blue-200 z-50 xs:!text-sm">
                                    {dropdownTitle && (
                                        <div className="py-4 sm:px-6 px-3 leading-5 flex justify-between items-center border-b border-black-200">
                                            <div className="p2 !text-black-800">{dropdownTitle}</div>{' '}
                                            <DropdownCloseIcon
                                                onClick={() => {
                                                    setOptionsVisible(false);
                                                }}
                                            />
                                        </div>
                                    )}
                                    <div className="py-4">
                                        <div className="dropdown-scrollbar sm:px-6 px-3 overflow-auto max-h-[150px] space-y-1">
                                            {filteredOptions.length === 0 && query !== '' ? (
                                                <div className="relative cursor-default select-none py-2 px-4 text-gray-700">Nothing found.</div>
                                            ) : (
                                                filteredOptions.map((option, idx) => (
                                                    <Combobox.Option key={idx} className={({ active }) => `relative p1 !text-black-800 rounded-sm cursor-default select-none py-2 px-4 ${active ? 'bg-black-200' : 'text-black-800'}`} value={option}>
                                                        {({ selected, active }) => (
                                                            <>
                                                                <span className={`block truncate `}>
                                                                    {option.title} <span className="ml-1 !text-new-pink p2">{option.isRecentlyAdded && '(Recently Added)'}</span>
                                                                </span>
                                                            </>
                                                        )}
                                                    </Combobox.Option>
                                                ))
                                            )}
                                        </div>
                                        {showCreateNewOptionButton && (
                                            <div className="sm:px-6 px-3">
                                                <AppButton className="flex space-x-2 items-center justify-center !w-full mt-4" onClick={handleCreateNew}>
                                                    <AddIcon />
                                                    <span>Create New</span>
                                                </AppButton>
                                            </div>
                                        )}
                                    </div>
                                </Combobox.Options>
                            </Transition>
                        </div>
                    );
                }}
            </Combobox>
        </div>
    );
});

ConsentAutoCompleteInput.displayName = 'ConsentConsentAutoCompleteInput';
export default ConsentAutoCompleteInput;