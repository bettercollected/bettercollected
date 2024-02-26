import type {Meta, StoryObj} from '@storybook/react';
import MenuDropdown from "@Components/Common/Navigation/MenuDropdown/MenuDropdown";
import React from "react";

const meta: Meta<typeof MenuDropdown> = {
    title: 'Common/MenuDropDown',
    component: MenuDropdown,
    parameters: {
        layout: 'centered'
    },
    tags: ['autodocs'],
    argTypes: {}
};

export default meta;
type Story = StoryObj<typeof MenuDropdown>;

const items = ['Item 1', 'Item 2', 'Item 3']

const DropdownItems = () => {
    return <div className={'flex flex-col '}>
        {items.map((item: any, index) => {
            return <span className={'hover:bg-black-200 px-3 py-2'} key={'index'}>{item}</span>
        })}
    </div>
}

export const Default: Story = {
    args: {
        menuTitle: 'MenuDropDown ToolTip',
        menuContent: <div className={'font-normal text-xl'}> Pick item from Dropdown </div>,
        children: <DropdownItems/>,
        size: 'medium',
        showIconBtnEffect: true,
        showExpandMore: true
    }
};



