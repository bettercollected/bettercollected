import React from 'react';

import { Button } from '@app/shadcn/components/ui/button';

interface Props {
    query: string;
    setQuery: (query: string) => void;
    onSearch: (query: string) => void;
}
function PhotoSearch({ setQuery, query, onSearch }: Props) {
    // Handler for form submission
    const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
        e.preventDefault();
        onSearch(query);
    };

    return (
        <form onSubmit={handleSubmit} className="flex items-center space-x-2">
            <label className=" w-full">
                <input
                    className="placeholder:theme-text-subtitle-1 theme-border-default  focus:theme-border-primary w-full rounded-md border py-2 pl-3 pr-3 focus:outline-none focus:ring-1 sm:text-sm"
                    placeholder="Search for an image"
                    type="text"
                    name="search"
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    autoFocus={true}
                />
            </label>
            <Button variant="secondary" type="submit">
                Search
            </Button>
        </form>
    );
}

export default PhotoSearch;
