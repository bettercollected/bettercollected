import React, { useEffect, useState } from 'react';

import { Input } from '@app/shadcn/components/ui/input';
import { SearchIcon } from 'lucide-react';
import { useDebounceValue } from 'usehooks-ts';

interface Props {
    query: string;
    setQuery: (query: string) => void;
    onSearch: (query: string) => void;
    initialPhotoSearchQuery?: string;
    placeholder?: string;
    className?: string;
}
function PhotoSearch({ setQuery, query, onSearch, initialPhotoSearchQuery, placeholder, className }: Props) {
    const [inputVal, setInputVal] = useState(query);
    const [debouncedInputValue] = useDebounceValue(inputVal, 500);

    useEffect(() => {
        initialPhotoSearchQuery && onSearch(initialPhotoSearchQuery);
    }, [initialPhotoSearchQuery]);

    useEffect(() => {
        onSearch(debouncedInputValue);
        initialPhotoSearchQuery && !debouncedInputValue && onSearch(initialPhotoSearchQuery);
    }, [debouncedInputValue]);

    // Handler for form submission
    const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
        e.preventDefault();
        onSearch(query);
    };

    return (
        <form onSubmit={handleSubmit} className={`flex h-10 items-center  space-x-2 md:w-[248px] ${className}`}>
            <label className=" w-full relative">
                <SearchIcon className="text-black-900 h-4 w-4 stroke-[2px] absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
                <Input
                    className="placeholder:text-black-400 border-black-200 focus-visible:ring-0 focus-visible:border-black-400 h-10 w-full rounded-lg pl-9 py-2 pr-3 sm:text-sm bg-white"
                    placeholder={placeholder ? placeholder : 'Search'}
                    type="text"
                    name="search"
                    value={inputVal}
                    onChange={(e: any) => setInputVal(e.target.value)}
                    autoFocus={true}
                />
            </label>
        </form>
    );
}

export default PhotoSearch;
