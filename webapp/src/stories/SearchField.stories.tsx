import type {Meta, StoryObj} from '@storybook/react';
import MenuDropdown from "@Components/Common/Navigation/MenuDropdown/MenuDropdown";
import React from "react";
import SearchInput from "@Components/Common/Search/SearchInput";

const meta: Meta<typeof SearchInput> = {
    title: 'Common/SearchField',
    component: SearchInput,
    parameters: {
        layout: 'centered'
    },
    tags: ['autodocs'],
    argTypes: {}
};

export default meta;
type Story = StoryObj<typeof SearchInput>;


export const SearchInputField: Story = {
    args: {
        placeholder: 'StoryBook Placeholder',
        handleSearch: () => {
        }
    }
};



