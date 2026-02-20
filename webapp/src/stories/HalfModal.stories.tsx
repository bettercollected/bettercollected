import HeaderModalWrapper from "@Components/Modals/ModalWrappers/HeaderModalWrapper";

import { Button } from '@app/shadcn/components/ui/button';
import { AppInput } from "@app/shadcn/components/ui/input";
import type { Meta, StoryObj } from '@storybook/react';


const meta: Meta<typeof HeaderModalWrapper> = {
    title: 'Common/Modal',
    component: HeaderModalWrapper,
    parameters: {
        layout: 'centered'
    },
    tags: ['autodocs'],
    argTypes: {},
    decorators: (Story) => <div className={'relative'}><Story /></div>
};

export default meta;
type Story = StoryObj<typeof HeaderModalWrapper>;

const Content = () => <div className={'flex flex-col p-2 gap-4'}>
    <h1 className={'text-xl font-semibold'}>Modal Example</h1>
    <p className={'text-sm text-black-700 '}>It is a modal component story that shows how this component renders actually in bettercollected project</p>
    <AppInput placeholder={'Enter a text'} />
    <Button size="medium">Enter</Button>
</div>

export const HalfScreenModal = {
    args: {
        children: <Content />,
        headerTitle: 'Half Screen Modal'
    }
}


