import React from 'react';

import SubmissionCard from '@app/components/cards/submission-card';
import EmptyFormsView from '@app/components/dashboard/empty-form';

const SubmissionsGrid = ({ responseObject }: any) => {
    return (
        <>
            {Object.values(responseObject).length === 0 && <EmptyFormsView />}
            {!!Object.values(responseObject).length &&
                Object.values(responseObject).map((response: any, idx: any) => {
                    return (
                        <div key={idx} className="mb-4">
                            <h1 className="text-xl font-semibold text-gray-700 mb-6 mt-6 inline-block pb-3 border-b-[1px] border-gray-300">
                                {response.title} ({response.responses?.length})
                            </h1>
                            <div className="grid grid-cols-1 md:grid-cols-2 3xl:grid-cols-3 4xl:grid-cols-4 gap-8">
                                {response.responses?.map((form: any) => (
                                    <SubmissionCard form={form} key={form.responseId} />
                                ))}
                            </div>
                        </div>
                    );
                })}
        </>
    );
};

export default SubmissionsGrid;
