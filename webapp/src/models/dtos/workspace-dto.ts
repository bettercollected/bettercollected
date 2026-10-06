// src/models/dtos/workspaceDto.ts
import { FormTheme } from '@app/constants/theme';

export type CustomDomainStatus = 'pending_dns' | 'provisioning' | 'ready' | 'attention_required' | 'suspended' | 'deleting';

export interface CustomDomainDnsRecord {
    name: string;
    type: 'TXT' | 'CNAME' | string;
    value: string;
    purpose: 'ownership' | 'routing' | string;
    help: string;
}

export interface CustomDomainCheck {
    type: 'ownership' | 'routing' | 'certificate' | 'origin' | string;
    status: 'pending' | 'passing' | 'failing' | string;
    error_code: string | null;
    message: string | null;
    observed_at: string | null;
    next_check_at: string | null;
}

export interface WorkspaceDto {
    title: string;
    workspaceName: string;
    description: string;
    // the billing owner: the account the workspace's plan is billed to
    ownerId: string;
    // in the signed-in user's own workspace list: whether they are an owner
    isOwner?: boolean;
    profileImage?: string;
    bannerImage?: string;
    customDomain?: string;
    dashboardAccess?: string;
    default?: string;
    disabled?: string;
    theme?: {
        primary_color: string;
        accent_color: string;
        text_color: string;
    };
    privacyPolicy?: string;
    termsOfService?: string;
    mailSettings?: string | null;
    id: string;
    isPro?: boolean;
    customDomainVerified?: boolean;
    // Mirrored from the custom-domain service when the workspace's domain is
    // registered there (null on the legacy certificate-server path).
    customDomainId?: string | null;
    customDomainStatus?: CustomDomainStatus | null;
    customDomainDnsRecords?: CustomDomainDnsRecord[] | null;
    customDomainChecks?: CustomDomainCheck[] | null;
    // Saved custom form themes (workspace "brand kit" palettes).
    customThemes?: FormTheme[];
}

export interface WorkspaceInvitationDto {
    invitationToken: string;
    email: string;
    createdAt: string;
    expiry: number;
    // Add any other relevant properties here
}

export const initWorkspaceDto: WorkspaceDto = {
    title: 'My title',
    workspaceName: 'ankit-sapkota',
    description: 'Description',
    ownerId: '63ca5518b613f81e118e3d8c',
    profileImage: '',
    bannerImage: '',
    customDomain: '',
    theme: {
        primary_color: '',
        accent_color: '',
        text_color: ''
    },
    privacyPolicy: '',
    termsOfService: '',
    mailSettings: '',
    id: '63ca5518b613f81e118e3d8d',
    isPro: false
};
