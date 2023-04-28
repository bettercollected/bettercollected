import React, { useEffect, useState } from 'react';

import { Share } from '@mui/icons-material';
import { Box, IconButton, Toolbar, Tooltip, Typography } from '@mui/material';
import { toast } from 'react-toastify';

import BreadcrumbsRenderer from '@app/components/form/renderer/breadcrumbs-renderer';
import { Close } from '@app/components/icons/close';
import { Copy } from '@app/components/icons/copy';
import { ShareIcon } from '@app/components/icons/share-icon';
import FormDrawer from '@app/components/sidebar/form-drawer';
import MuiDrawer from '@app/components/sidebar/mui-drawer';
import SidebarLayout from '@app/components/sidebar/sidebar-layout';
import Button from '@app/components/ui/button';
import ShareView from '@app/components/ui/share-view';
import environments from '@app/configs/environments';
import { useBreakpoint } from '@app/lib/hooks/use-breakpoint';
import { useCopyToClipboard } from '@app/lib/hooks/use-copy-to-clipboard';
import { BreadcrumbsItem } from '@app/models/props/breadcrumbs-item';
import { initialFormState, setForm } from '@app/store/forms/slice';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { toEndDottedStr, toMidDottedStr } from '@app/utils/stringUtils';

export default function FormPageLayout(props: any) {
    const form = useAppSelector((state) => state.form);
    const workspace = useAppSelector((state) => state.workspace);

    const dispatch = useAppDispatch();
    const [_, copyToClipboard] = useCopyToClipboard();

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

    const clientHostUrl = `${environments.CLIENT_DOMAIN.includes('localhost') ? 'http' : 'https'}://${environments.CLIENT_DOMAIN}/${workspace.workspaceName}/forms/${customUrl}`;
    const customDomainUrl = `${environments.CLIENT_DOMAIN.includes('localhost') ? 'http' : 'https'}://${workspace.customDomain}/forms/${customUrl}`;
    const shortenedClientHostUrl = toMidDottedStr(clientHostUrl, 8);
    const shortenedCustomDomainUrl = toMidDottedStr(customDomainUrl, 8);

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

    return (
        <SidebarLayout DrawerComponent={FormDrawer}>
            <div className="py-5 w-full relative">
                <div className="flex z-10 justify-between">
                    <div className=" flex items-center space-x-4">
                        <BreadcrumbsRenderer items={breadcrumbsItem} />
                    </div>
                    <div onClick={handleDrawerToggle}>
                        <IconButton>
                            <Share />
                        </IconButton>
                    </div>
                </div>
                <div className="absolute xl:left-[-40px] px-5 xl:px-10 pb-10 mt-16 top-0 w-full py-6 xl:max-w-289-calc-289">{props.children}</div>
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
                                <ShareView url={clientHostUrl} showCopy={false} showBorder={false} />

                                <div className="mt-10">
                                    <div className="body1 pb-4">Form Links</div>
                                    <div className="text-black-900 space-x-4 underline max-w-full body4 items-center rounded p-4 flex bg-brand-100">
                                        <Tooltip title={clientHostUrl}>
                                            <Typography className="truncate">{clientHostUrl}</Typography>
                                        </Tooltip>
                                    </div>
                                    <div className="flex w-full mt-4 justify-end">
                                        <Button
                                            variant="outline"
                                            onClick={() => {
                                                copyToClipboard(`${environments.CLIENT_DOMAIN.includes('localhost') ? 'http' : 'https'}://${environments.CLIENT_DOMAIN}/${workspace.workspaceName}/forms/${customUrl}`);
                                                toast('Form URL Copied', {
                                                    type: 'info'
                                                });
                                            }}
                                        >
                                            Copy Link
                                        </Button>
                                    </div>

                                    {isCustomDomain && (
                                        <>
                                            <div className="text-black-900 space-x-4 mt-4 underline w-fit body4 items-center rounded p-4 flex bg-brand-100">
                                                <Tooltip title={customDomainUrl}>
                                                    <Typography className="truncate">{customDomainUrl}</Typography>
                                                </Tooltip>
                                            </div>
                                            <div className="flex w-full mt-4 justify-end">
                                                <Button
                                                    variant="outline"
                                                    onClick={() => {
                                                        copyToClipboard(`${environments.CLIENT_DOMAIN.includes('localhost') ? 'http' : 'https'}://${workspace.customDomain}/forms/${customUrl}`);
                                                        toast('Form URL Copied', {
                                                            type: 'info'
                                                        });
                                                    }}
                                                >
                                                    Copy Link
                                                </Button>
                                            </div>
                                        </>
                                    )}
                                </div>
                            </div>
                        </Box>
                    </>
                </MuiDrawer>
            </div>
        </SidebarLayout>
    );
}
