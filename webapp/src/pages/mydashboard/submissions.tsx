import { useEffect, useState } from 'react';

import { info } from 'console';

import { ShareIcon } from '@app/components/icons/share-icon';
import Layout from '@app/components/sidebar/layout';
import FullScreenLoader from '@app/components/ui/fullscreen-loader';
import useUser from '@app/lib/hooks/use-authuser';
import { useBreakpoint } from '@app/lib/hooks/use-breakpoint';
import { useGetSubmissionsQuery } from '@app/store/google/api';
import { toEndDottedStr } from '@app/utils/stringUtils';

export default function MySubmissions() {
    const { isLoading } = useUser();

    const submissionsQuery = useGetSubmissionsQuery(null);
    const breakpoint = useBreakpoint();

    const [responseObject, setResponseObject] = useState({});

    const convertToClientForm = (formsArray: Array<any>) => {
        const responseMap = formsArray.reduce(function (accumulator, value) {
            if (!accumulator[value.formId]) {
                accumulator[value.formId] = {
                    title: value.formTitle,
                    responses: [value]
                };
            } else {
                accumulator[value.formId].responses.push(value);
            }
            return accumulator;
        }, Object.create(null));

        return responseMap;
    };

    useEffect(() => {
        if (!submissionsQuery.isLoading && !!submissionsQuery.data.payload.content) {
            const responseMapObject = convertToClientForm(submissionsQuery.data.payload.content);
            setResponseObject(responseMapObject);
        }
    }, [submissionsQuery]);

    if (isLoading || submissionsQuery.isLoading) return <FullScreenLoader />;

    const CardRenderer = () => {
        return (
            <>
                {!!Object.values(responseObject).length &&
                    Object.values(responseObject).map((response: any, idx: any) => {
                        return (
                            <div key={idx} className="mb-4">
                                <h1 className="text-xl font-semibold text-gray-700 mb-6 mt-6 inline-block pb-3 border-b-[1px] border-gray-300">
                                    {response.title} ({response.responses.length})
                                </h1>
                                <div className="grid grid-cols-1 md:grid-cols-2 3xl:grid-cols-3 4xl:grid-cols-4 gap-8">
                                    {response.responses.map((form: any) => {
                                        return (
                                            <div
                                                key={form.responseId}
                                                className="flex flex-row items-center justify-between h-full gap-8 p-5 border-[1px] border-neutral-300 hover:border-blue-500 drop-shadow-sm hover:drop-shadow-lg transition cursor-pointer bg-white rounded-[20px]"
                                            >
                                                <div className="flex flex-col justify-start h-full overflow-hidden">
                                                    <p className="text-sm text-gray-400 italic ">{['xs'].indexOf(breakpoint) !== -1 ? toEndDottedStr(form.responseId, 15) : toEndDottedStr(form.responseId, 30)}</p>
                                                    <p className="text-xl text-grey mb-4 p-0">{['xs', 'sm'].indexOf(breakpoint) !== -1 ? toEndDottedStr(form.formTitle, 15) : toEndDottedStr(form.formTitle, 30)}</p>
                                                    {form?.description && (
                                                        <p className="text-base text-softBlue m-0 p-0 w-full">
                                                            {['xs', 'sm'].indexOf(breakpoint) !== -1 ? toEndDottedStr(form.description, 45) : ['md'].indexOf(breakpoint) !== -1 ? toEndDottedStr(form.description, 80) : toEndDottedStr(form.description, 140)}
                                                        </p>
                                                    )}
                                                    {!form?.description && <p className="text-base text-softBlue m-0 p-0 w-full italic">Form description not available.</p>}
                                                    <p className="italic w-fit bg-blue-100 text-gray-700 text-[10px] px-2 py-1 rounded-lg">{!form.dataOwnerIdentifier ? 'Anonymous' : form.dataOwnerIdentifier}</p>
                                                </div>
                                            </div>
                                        );
                                    })}
                                </div>
                            </div>
                        );
                    })}
            </>
        );
    };

    // UI for forms
    const MyRecentForms = () => {
        return (
            <div>
                <h1 className="font-semibold text-2xl mb-4">Submissions</h1>
            </div>
        );
    };

    return (
        <Layout>
            <MyRecentForms />
            <CardRenderer />
        </Layout>
    );
}
