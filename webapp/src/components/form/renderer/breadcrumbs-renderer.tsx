import React from 'react';

function BreadcrumbRenderer(props: any) {
    const { breadcrumbsItem } = props;

    return (
        <div className="max-h-[100vh] overflow-auto mb-4">
            <nav className="flex mt-3 px-6 md:px-0" aria-label="Breadcrumb">
                <ol className="flex items-center space-x-1 md:space-x-3">
                    {breadcrumbsItem.map((item: any, idx: number) => {
                        return (
                            <li key={idx} className="inline-flex items-center">
                                <span aria-hidden onClick={!!item.onClick ? item.onClick : () => {}} className="cursor-pointer inline-flex items-center text-sm font-medium text-gray-700 hover:text-gray-900 dark:text-gray-400 dark:hover:text-white">
                                    {item.icon}
                                    {item.title}
                                    {idx !== breadcrumbsItem.length - 1 && (
                                        <svg className="w-6 h-6 text-gray-400" fill="currentColor" viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg">
                                            <path fillRule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clipRule="evenodd"></path>
                                        </svg>
                                    )}
                                </span>
                            </li>
                        );
                    })}
                </ol>
            </nav>
        </div>
    );
}

export default React.memo(BreadcrumbRenderer);
