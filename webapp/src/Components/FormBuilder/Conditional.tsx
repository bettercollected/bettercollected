import React, { Fragment, useState } from 'react';

import _ from 'lodash';

import { FieldRequired } from '@Components/UI/FieldRequired';
import { Combobox, Listbox } from '@headlessui/react';
import { Star, StarBorder } from '@mui/icons-material';

import { ArrowDown } from '@app/components/icons/arrow-down';
import { FormBuilderConditionalComparison } from '@app/models/dtos/formBuilder';

interface IRatingFieldProps {
    field: any;
    id: any;
    position: any;
}

const People = [
    { value: 'Durward Reynolds' },
    { value: 'Kenton Towne' },
    { value: 'Therese Wunsch' },
    {
        value: 'Katelyn Rohan asdasdasd asdasd asdasd aasdwww'
    }
];

const Comparisons = [
    {
        type: FormBuilderConditionalComparison.IS_EQUAL,
        value: 'Is'
    },
    {
        type: FormBuilderConditionalComparison.IS_NOT_EQUAL,
        value: 'Is Not'
    },
    {
        type: FormBuilderConditionalComparison.IS_EMPTY,
        value: 'Is Empty'
    },
    {
        type: FormBuilderConditionalComparison.IS_NOT_EMPTY,
        value: 'Is Not Empty'
    }
];

export default function Conditional({ field, id, position }: IRatingFieldProps) {
    return (
        <div tabIndex={0} id={id} className="flex flex-col gap-4 mt-6 w-fit p-4 border-2 border-dashed border-black-300 rounded-lg">
            <IfBlock />
            <ThenBlock />
        </div>
    );
}

const IfBlock = () => {
    return (
        <div className={'flex flex-col gap-2 p-4 rounded-lg bg-new-white-200'}>
            <h1 className={'text-pink-500 text-sm'}>IF</h1>
            <div className={'flex flex-row gap-2 '}>
                <ConditionalListDropDown firstState={People[0]} allState={People} />
                <ConditionalListDropDown size={'small'} firstState={Comparisons[0]} allState={Comparisons} />
                <ConditionalListDropDown firstState={{ value: 'Value' }} allState={People} />
            </div>
        </div>
    );
};

const ThenBlock = () => {
    return (
        <div className={'flex flex-col gap-2 p-4 bg-new-white-200 rounded-lg'}>
            <h1 className={'text-pink-500 text-sm'}>THEN</h1>
            <div className={'flex flex-row gap-2 '}>
                <ConditionalListDropDown firstState={{ value: 'State' }} allState={People} />
                <ConditionalListDropDown size={'small'} firstState={{ value: 'Select a Field' }} allState={Comparisons} />
            </div>
        </div>
    );
};

interface IConditionalListDropDown {
    size?: string;
    className?: string;
    firstState: any;
    allState: any;
}

const ConditionalListDropDown = ({ size = 'large', className, firstState, allState }: IConditionalListDropDown) => {
    const [selectedState, setSelectedState] = useState(firstState);

    return (
        <Listbox value={selectedState} onChange={setSelectedState}>
            {({ open }) => {
                return (
                    <div className={`relative bg-white ${size === 'small' ? 'w-[160px]' : 'w-[280px]'} ${className}`}>
                        <Listbox.Button>
                            <div className={`flex justify-between border border-black-400 rounded p-2 text-sm font-normal text-black-800 ${open && 'border-black-900 '} ${size === 'small' ? 'w-[160px]' : 'w-[280px]'} `}>
                                {selectedState.value}
                                <ArrowDown className={`${open ? 'rotate-180' : ''}`} />
                            </div>
                        </Listbox.Button>
                        <Listbox.Options>
                            <div className={'w-full mt-2 bg-white shadow-input py-2 gap-4 absolute z-10 rounded-lg'}>
                                {allState.map((state: any, index: number) => (
                                    <Listbox.Option key={index} value={state} as={Fragment}>
                                        {({ active, selected }) => <li className={`px-4 py-2 cursor-pointer truncate text-ellipsis text-base font-normal text-black-800 ${active ? 'bg-black-200 ' : 'bg-white text-black-800'}`}>{state.value}</li>}
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
