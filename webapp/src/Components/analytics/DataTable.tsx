import React from 'react';
import Flag from 'react-world-flags';
import { getBrowserIcon, getDeviceIcon, getOSIcon } from './icons';
import { FaGlobe } from 'react-icons/fa';

interface DataTableProps {
    title: string;
    data: { x: string; y: number }[];
    showCountryFlag?: boolean;
}

const DataTable: React.FC<DataTableProps> = ({ title, data, showCountryFlag }) => {
    const regionNames = new Intl.DisplayNames(['en'], { type: 'region' });

    const getIcon = (item: string) => {
        switch (title) {
            case 'Browsers':
                return getBrowserIcon(item);
            case 'Devices':
                return getDeviceIcon(item);
            case 'Operating System':
                return getOSIcon(item);
            default:
                return FaGlobe;
        }
    };

    return (
        <div className="rounded-lg bg-white p-4 shadow-md">
            <h3 className="mb-4 text-xl font-semibold">{title}</h3>
            <ul>
                {data.map((item, index) => {
                    const Icon = getIcon(item.x);

                    return (
                        <li key={index} className="flex items-center space-x-3 py-2">
                            {showCountryFlag ? <Flag code={item.x} style={{ width: '24px', height: '16px', marginRight: '8px' }} className="mr-2" /> : <Icon />}
                            <span className="font-medium">{showCountryFlag ? regionNames.of(item.x) || 'Unknown' : item.x || 'None'}</span>
                            <span className="ml-auto text-gray-500">{item.y}</span>
                        </li>
                    );
                })}
            </ul>
        </div>
    );
};

export default DataTable;
