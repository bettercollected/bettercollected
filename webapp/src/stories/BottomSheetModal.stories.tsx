import type {Meta, StoryObj} from '@storybook/react';
import WorkspaceFormCard from "@app/components/workspace-dashboard/workspace-form-card";
import BottomSheetModalWrapper from "@Components/Modals/BottomSheetModals/BottomSheetModalWrapper";


const meta: Meta<typeof BottomSheetModalWrapper> = {
    title: 'Common/BottomSheetModal',
    component: BottomSheetModalWrapper,
    parameters: {
        layout: 'centered'
    },
    tags: ['autodocs'],
    argTypes: {},
    decorators: (Story) => <div className={'relative'}><Story/></div>
};

export default meta;
type Story = StoryObj<typeof BottomSheetModalWrapper>;

const Content = () => <div className={'flex flex-col p-2 gap-4'}>
    <h1 className={'text-xl font-semibold'}>BottomSheetModal Example</h1>
    <p className={'text-sm text-black-700 '}>It is a bottom sheet modal component story that shows how this component renders actually</p>
</div>

export const Modal = {
    args: {
        children: <Content/>,
        className: 'w-[1630px]'
    }
}


