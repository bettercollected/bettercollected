import type {Meta, StoryObj} from '@storybook/react';
import React from "react";
import DashboardDrawer from '@app/components/sidebar/dashboard-drawer';
import {INavbarItem} from "@app/models/props/navbar";
import {FormIcon} from "@Components/Common/Icons/Form/FormIcon";
import ResponderIcon from "@Components/Common/Icons/Dashboard/Responder";
import {TemplateIcon} from "@app/components/icons/template";
import Globe from "@app/components/icons/flags/globe";
import {store} from '@app/store/store';
import {setAuth} from '@app/store/auth/slice';


const meta: Meta<typeof DashboardDrawer> = {
    title: 'Dashboard/Drawer',
    component: DashboardDrawer,
    parameters: {
        layout: 'centered'
    },
    tags: ['autodocs'],
    argTypes: {},
    decorators: (Story) => {
        store.dispatch(setAuth({isAdmin: true}))
        return <><Story/></>
    }
};

export default meta;
type Story = StoryObj<typeof DashboardDrawer>;

const topNavList: Array<INavbarItem> = [

    {
        key: 'forms',
        name: 'Forms',
        url: `workspace/forms`,
        icon: <FormIcon/>
    },
    {
        key: 'responders',
        name: 'Responders',
        url: `workspace/responders-groups`,
        icon: <ResponderIcon/>
    },
    {
        key: 'templates',
        name: 'Templates',
        url: `workspace/templates`,
        icon: <TemplateIcon className={'stroke-2'}/>
    }
];
const bottomNavList: Array<INavbarItem> = [
    {
        key: 'urls',
        name: 'Manage URLs',
        url: ``,
        icon: <Globe/>,
    }
];

export const Drawer: Story = {
    args: {
        topNavList: topNavList,
        bottomNavList: bottomNavList
    }
};



