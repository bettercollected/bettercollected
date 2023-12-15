import type {Meta, StoryObj} from '@storybook/react';
import GenericHalfModal from "@Components/Common/Modals/GenericHalfModal";
import ParamTab, {TabPanel} from "@app/components/ui/param-tab";
import WorkspaceDetails from "@Components/Workspace/Settings/WorkspaceDetails";
import ManageURLs from "@Components/Workspace/Settings/ManageURLs";


const meta: Meta<typeof ParamTab> = {
    title: 'Common/ParamTab',
    component: ParamTab,
    parameters: {
        layout: 'centered'
    },
    tags: ['autodocs'],
    argTypes: {},
    decorators: (Story) => <div className={'bg-white p-2'}><Story/></div>
};

export default meta;
type Story = StoryObj<typeof ParamTab>;

const Content1 = () => <div>
    <p className={'text-sm text-black-700 '}>It is content 1 of param-tabs component to render on storybook.</p>
</div>
const Content2 = () => <div>
    <p className={'text-sm text-black-700 '}>It is content 2 of param-tabs component to render on storybook.</p>

</div>
const Content3 = () => <div>
    <p className={'text-sm text-black-700 '}>It is content 3 of param-tabs component to render on storybook.</p>

</div>

const tabMenu = [
    {
        title: 'Workspace Details',
        path: 'workspace-details'
    },
    {
        title: 'Other Settings',
        path: 'other-settings'
    },
    {
        title: 'Manage URLs',
        path: 'manage-url'
    }
];

const ChildrenComponent = () => <div className={'p-2'}>
    <TabPanel>
        <Content1/>
    </TabPanel>
    <TabPanel>
        <Content2/>
    </TabPanel>
    <TabPanel>
        <Content3/>
    </TabPanel>
</div>

export const ParamTabsStory: Story = {
    args: {
        initialIndex: 0,
        tabMenu: tabMenu,
        isRouteChangeable: false,
        children: <ChildrenComponent/>
    }
}
export const ParamTabsStoryWithLastIndex: Story = {
    args: {
        initialIndex: 2,
        tabMenu: tabMenu,
        isRouteChangeable: true,
        children: <ChildrenComponent/>
    }
}



