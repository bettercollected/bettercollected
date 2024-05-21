import React, { useEffect, useState } from 'react';

import { SearchIcon } from '@app/views/atoms/Icons/Search';
import { TextField } from '@mui/material';
import { useDebounceValue } from 'usehooks-ts';

interface Props {
    query: string;
    setQuery: (query: string) => void;
    onSearch: (query: string) => void;
    initialPhotoSearchQuery?: string;
}
function PhotoSearch({ setQuery, query, onSearch, initialPhotoSearchQuery }: Props) {
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
        <form onSubmit={handleSubmit} className="flex items-center space-x-2  md:w-[227px]">
            <label className=" w-full">
                <TextField
                    sx={{
                        height: '40px',
                        padding: 0,
                        '& .MuiOutlinedInput-root': {
                            borderRadius: '8px',
                            '& fieldset': {
                                borderColor: '#EEEEEE'
                            },
                            '&.Mui-focused fieldset': {
                                borderColor: '#4D4D4D',
                                borderWidth: '1px'
                            },
                            '&:hover fieldset': {
                                borderColor: '#4D4D4D'
                            }
                        },
                        '& .MuiInputBase-root': {
                            height: '40px',
                            gap: '4px'
                        }
                    }}
                    InputProps={{
                        sx: {
                            backgroundColor: '#F6F6F6'
                        },
                        startAdornment: <SearchIcon className="text-black-900 h-4 w-4 stroke-[2px]" />
                    }}
                    className="placeholder:text-black-400 bg-black-100 border-black-200 focus:ring-none h-full w-full rounded-lg border py-2 pl-3 pr-3 focus:outline-none sm:text-sm"
                    placeholder="Search"
                    type="text"
                    name="search"
                    value={inputVal}
                    onChange={(e) => setInputVal(e.target.value)}
                    autoFocus={true}
                />
            </label>
        </form>
    );
}

export default PhotoSearch;
