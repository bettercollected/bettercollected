import React, { useState } from 'react';

import Link from 'next/link';
import { useRouter } from 'next/router';

import { Feed, Settings } from '@mui/icons-material';
import { Divider, IconButton, Input, InputAdornment } from '@mui/material';
import Switch from '@mui/material/Switch';
import TextField from '@mui/material/TextField';

import { HistoryIcon } from '@app/components/icons/history';
import { SearchIcon } from '@app/components/icons/search';
import Layout from '@app/components/sidebar/layout';
import ParamTab from '@app/components/ui/param-tab';
import { TabPanel } from '@app/components/ui/tab';
import { useBreakpoint } from '@app/lib/hooks/use-breakpoint';
import globalServerProps from '@app/lib/serverSideProps';
import { toEndDottedStr } from '@app/utils/stringUtils';

enum FormTabs {
    FORM = 'Form',
    RESPONSE = 'Responses',
    SETTINGS = 'Settings'
}

export default function FormPage(props: any) {
    const { formId } = props;
    const breakpoint = useBreakpoint();
    const router = useRouter();

    const tabs = [
        {
            icon: <Feed />,
            path: 'form',
            title: 'Form'
        },
        {
            icon: <HistoryIcon className="w-[20px] h-[20px]" />,
            title: 'Responses',
            path: 'response'
        },
        {
            icon: <Settings />,
            title: 'Settings',
            path: 'settings'
        }
    ];

    const SettingsTabContent = () => (
        <div className="max-w-[600px]">
            <div className=" flex flex-col">
                <div className="text-xl font-bold text-black">Pinned</div>
                <div className="flex w-full justify-between items-center h-14 text-gray-800">
                    <div>Show this form in pinned section</div>
                    <Switch />
                </div>
            </div>
            <Divider className="mb-6 mt-2" />
            <div className=" flex flex-col ">
                <div className="text-xl font-bold text-black">Custom Url</div>
                <div className="flex w-full items-center justify-between text-gray-800">
                    <div>Something to show in url instead of id of form</div>
                    <TextField size="small" name="search-input" placeholder="Custom-url" value={'Hello'} onChange={() => {}} className={'w-full max-w-[250px]'} />
                </div>
            </div>
        </div>
    );

    const FormTabContent = () => (
        <div className="w-full">
            <div>You can preview the form by clicking the link below.</div>
            <Link href={`http://localhost:3000/forms/${formId}`}>
                <div className="flex">
                    <div className="text-blue-500 hover:underline  cursor-pointer ">Link to form.</div>
                    🔗
                </div>
            </Link>
        </div>
    );

    return (
        <Layout>
            <div className="max-h-[100vh] overflow-auto">
                <nav className="flex mt-3 px-0 md:px-0" aria-label="Breadcrumb">
                    <ol className="inline-flex items-center space-x-1 md:space-x-3">
                        <li className="inline-flex items-center">
                            <span aria-hidden onClick={() => router.push('/dashboard')} className="cursor-pointer inline-flex items-center text-sm font-medium text-gray-700 hover:text-gray-900 dark:text-gray-400 dark:hover:text-white">
                                <svg className="w-4 h-4 mr-2" fill="currentColor" viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg">
                                    <path d="M10.707 2.293a1 1 0 00-1.414 0l-7 7a1 1 0 001.414 1.414L4 10.414V17a1 1 0 001 1h2a1 1 0 001-1v-2a1 1 0 011-1h2a1 1 0 011 1v2a1 1 0 001 1h2a1 1 0 001-1v-6.586l.293.293a1 1 0 001.414-1.414l-7-7z"></path>
                                </svg>
                                Forms
                            </span>
                        </li>
                        <li aria-current="page">
                            <div className="flex items-center">
                                <svg className="w-6 h-6 text-gray-400" fill="currentColor" viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg">
                                    <path fill-rule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clip-rule="evenodd"></path>
                                </svg>
                                <span className="ml-1 text-sm font-medium text-gray-500 md:ml-2 dark:text-gray-400">{['xs'].indexOf(breakpoint) !== -1 ? toEndDottedStr(formId, 10) : formId}</span>
                            </div>
                        </li>
                    </ol>
                </nav>
            </div>
            <div className="flex flex-col justify-center">
                <ParamTab tabMenu={tabs}>
                    <TabPanel className="focus:outline-none" key="form">
                        <FormTabContent />
                    </TabPanel>
                    <TabPanel className="focus:outline-none" key="submissions">
                        <div>Submission tab content</div>
                    </TabPanel>
                    <TabPanel className="focus:outline-none" key="settings">
                        <SettingsTabContent />
                    </TabPanel>
                </ParamTab>
            </div>
        </Layout>
    );
}

export async function getServerSideProps(_context: any) {
    const globalProps = (await globalServerProps(_context)).props;
    const { form_id } = _context.query;
    console.info(form_id);
    return {
        props: {
            formId: form_id
        }
    };
}
