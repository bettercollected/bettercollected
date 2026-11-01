import React from 'react';

import { useTranslation } from 'react-i18next';

import { useIntlLocale } from '@app/lib/hooks/use-intl-locale';
import { FaGlobe } from 'react-icons/fa';
import Flag from 'react-world-flags';
import { getBrowserIcon, getDeviceIcon, getOSIcon } from './icons';

interface DataTableProps {
    title: string;
    data: { x: string; y: number }[];
    showCountryFlag?: boolean;
    /** Which icons to draw; the title is only what the person reads. */
    kind?: 'browsers' | 'devices' | 'os';
}

const AnalyticsDataTable: React.FC<DataTableProps> = ({ title, data, showCountryFlag = false, kind }) => {
    const { t } = useTranslation();
    const regionNames = new Intl.DisplayNames([useIntlLocale()], { type: 'region' });

    const getIcon = (item: string): React.ElementType => {
        switch (kind) {
            case 'browsers':
                return getBrowserIcon(item);
            case 'devices':
                return getDeviceIcon(item);
            case 'os':
                return getOSIcon(item);
            default:
                return FaGlobe; // Default icon
        }
    };

    return (
        <div className="rounded border border-black-300 bg-white p-4">
            <h3 className="mb-4 text-xl font-semibold">{title}</h3>
            <ul>
                {data.map((item, index) => {
                    const Icon = getIcon(item.x);

                    return (
                        <li key={index} className="flex items-center space-x-3 py-2">
                            {showCountryFlag ? <Flag code={item.x} style={{ width: '24px', height: '16px', marginRight: '8px' }} className="mr-2" /> : <Icon />}
                            <span className="font-medium">
                                {showCountryFlag
                                    ? (() => {
                                        try {
                                            return regionNames.of(item.x) || t('ANALYTICS.UNKNOWN');
                                        } catch (error) {
                                            if (error instanceof RangeError) {
                                                return t('ANALYTICS.UNKNOWN');
                                            }
                                            throw error;
                                        }
                                    })()
                                    : item.x || 'None'}
                            </span>
                            <span className="ml-auto text-gray-500">{item.y}</span>
                        </li>
                    );
                })}
            </ul>
        </div>
    );
};

export default AnalyticsDataTable;
