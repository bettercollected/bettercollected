import type {Meta, StoryObj} from '@storybook/react';
import WorkspaceFormCard from "@app/components/workspace-dashboard/workspace-form-card";


const meta: Meta<typeof WorkspaceFormCard> = {
    title: 'Dashboard/WorkspaceFormCard',
    component: WorkspaceFormCard,
    parameters: {
        layout: 'centered'
    },
    tags: ['autodocs'],
    argTypes: {},
};

export default meta;
type Story = StoryObj<typeof WorkspaceFormCard>;

const formData = {
    formId: "651a4e28588b3f432a942b61",
    title: "New Form",
    settings: {
        pinned: true,
        customUrl: "string",
        private: false,
        hidden: true,
        provider: "string",
        disableBranding: true,
    },
    isPublished: false,
    consent: [],
    fields: [
        {
            id: "651a4e28588b3f432a942b61",
            title: "string",
            description: "string",
            value: "string",
            type: "text",
            tag: "h1",
        }
    ],
    groups: []
}

const workspaceData = {
    title: "Bettercollected",
    workspaceName: "template",
    description: "kjasdkjhakjsdh",
    customDomain: '',
    id: "650c021f6c1c0477088ec6ce",
    ownerId: "650c021f179c67f194e4db22",
    privacy_policy_url: 'https://bettercollected.com/legal/privacy-policy-2022.pdf',
    terms_of_service_url: 'https://bettercollected.com/legal/terms-and-conditions-2022.pdf',
    isPro: false
}

const publishedFormData = {...formData, isPublished: true}

export const DraftFormCard: Story = {
    args: {
        form: formData,
        workspace: workspaceData,
    }
};
export const PublishedFormCard: Story = {
    args: {
        form: publishedFormData,
        workspace: workspaceData,
    }
};

export const ResponderFormCard: Story = {
    args: {
        form: publishedFormData,
        workspace: workspaceData,
        isResponderPortal: true,
    }
};

export const HideVisibilityAndPinned: Story = {
    args: {
        form: publishedFormData,
        workspace: workspaceData,
        showPinned: false,
        showVisibility: false
    }
}



