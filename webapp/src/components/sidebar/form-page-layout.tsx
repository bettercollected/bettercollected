import React, { useEffect, useState } from 'react';

import Toolbar from '@Components/Common/Layout/Toolbar';
import { Share } from '@mui/icons-material';
import { Box, IconButton } from '@mui/material';

import CustomizeLink from '@app/components/cards/customizelink-card';
import BreadcrumbsRenderer from '@app/components/form/renderer/breadcrumbs-renderer';
import { Close } from '@app/components/icons/close';
import { useModal } from '@app/components/modal-views/context';
import FormDrawer from '@app/components/sidebar/form-drawer';
import MuiDrawer from '@app/components/sidebar/mui-drawer';
import SidebarLayout from '@app/components/sidebar/sidebar-layout';
import LinkView from '@app/components/ui/link-view';
import ShareView from '@app/components/ui/share-view';
import environments from '@app/configs/environments';
import { formCustomizeLink } from '@app/constants/Customize-domain';
import { useBreakpoint } from '@app/lib/hooks/use-breakpoint';
import { BreadcrumbsItem } from '@app/models/props/breadcrumbs-item';
import { initialFormState, setForm } from '@app/store/forms/slice';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { toEndDottedStr } from '@app/utils/stringUtils';

export default function FormPageLayout(props: any) {
    const form = useAppSelector((state) => state.form);
    const workspace = useAppSelector((state) => state.workspace);
    const { openModal } = useModal();
    const dispatch = useAppDispatch();
    useEffect(() => {
        dispatch(setForm(props.form));
        return () => {
            dispatch(setForm(initialFormState));
        };
    }, []);

    const isCustomDomain = !!workspace.customDomain;

    const [mobileOpen, setMobileOpen] = useState(false);

    const handleDrawerToggle = () => {
        setMobileOpen(!mobileOpen);
    };

    const customUrl = form?.settings?.customUrl || '';

    const clientHost = `${environments.CLIENT_DOMAIN.includes('localhost') ? 'http' : 'https'}://${environments.CLIENT_DOMAIN}/${workspace.workspaceName}/forms`;
    const customDomain = `${environments.CLIENT_DOMAIN.includes('localhost') ? 'http' : 'https'}://${workspace.customDomain}/forms`;
    const clientHostUrl = `${clientHost}/${customUrl}`;
    const customDomainUrl = `${customDomain}/${customUrl}`;
    const breakpoint = useBreakpoint();

    const breadcrumbsItem: Array<BreadcrumbsItem> = [
        {
            title: 'Dashboard',
            url: `/${props?.workspace?.workspaceName}/dashboard`
        },
        {
            title: 'Forms',
            url: `/${props?.workspace?.workspaceName}/dashboard/forms`
        },
        {
            title: ['xs'].indexOf(breakpoint) !== -1 ? toEndDottedStr(form?.title, 30) : form?.title || '',
            disabled: true
        }
    ];

    const links = [
        {
            url: clientHostUrl
        }
    ];

    const getFormLinks = () => {
        if (isCustomDomain) links.push({ url: customDomainUrl });
        return links;
    };

    return (
        <SidebarLayout DrawerComponent={FormDrawer}>
            <div className=" w-full relative">
                <div className="flex h-full z-10 justify-between">
                    <div className=" flex items-center h-full space-x-4">
                        <BreadcrumbsRenderer items={breadcrumbsItem} />
                    </div>
                    <div onClick={handleDrawerToggle}>
                        <IconButton>
                            <Share />
                        </IconButton>
                    </div>
                </div>
                <div className="absolute xl:left-[-40px] px-5 xl:px-10 pb-10 mt-14 top-0 w-full py-4 xl:max-w-289-calc-289">{props.children}</div>
                <MuiDrawer
                    mobileOpen={mobileOpen}
                    anchor="right"
                    handleDrawerToggle={handleDrawerToggle}
                    mobileDrawerDisplayProps={{ xs: 'block', sm: 'block', md: 'block', lg: 'block', xl: 'none' }}
                    desktopDrawerDisplayProps={{ xs: 'none', sm: 'none', md: 'none', lg: 'none', xl: 'block' }}
                >
                    <>
                        <Toolbar />
                        <Box sx={{ overflow: 'auto', height: '100%' }}>
                            <div className=" px-5 h-full py-6 relative w-full">
                                <Close onClick={handleDrawerToggle} className="absolute blocks lg:hidden right-5 top-5 cursor-pointer" />
                                <ShareView url={clientHostUrl} showCopy={false} showBorder={false} iconSize="small" />

                                <div className="mt-12">
                                    <div className="body1 mb-4 !leading-none ">Form Links</div>
                                    {getFormLinks().map((formLink: any) => (
                                        <LinkView key={formLink.url} url={formLink.url} toastMessage="Form URL Copied" className="flex flex-col mb-4" buttonClassName="!text-brand-500 !border-blue-200 hover:!bg-brand-200 " />
                                    ))}
                                </div>
                                <div className="my-12">
                                    <CustomizeLink
                                        title={formCustomizeLink.title}
                                        subtitle={formCustomizeLink.description}
                                        buttonText="Customize link"
                                        onClick={() => openModal('CUSTOMIZE_URL', { description: formCustomizeLink.description, url: isCustomDomain ? customDomain : clientHost })}
                                    />
                                </div>
                            </div>
                        </Box>
                    </>
                </MuiDrawer>
            </div>
        </SidebarLayout>
    );
}
