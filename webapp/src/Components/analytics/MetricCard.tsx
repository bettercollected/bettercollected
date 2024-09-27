import React from 'react';
import { FaArrowUp, FaArrowDown, FaArrowRight } from 'react-icons/fa';

interface MetricCardProps {
    title: string;
    value: string;
    percentage: string;
}

const MetricCard: React.FC<MetricCardProps> = ({ title, value, percentage }) => {
    const percentValue = parseFloat(percentage);

    let colorClass = '';
    let icon = <FaArrowRight />;

    if (percentValue > 0) {
        colorClass = 'text-green-500';
        icon = <FaArrowUp />;
    } else if (percentValue < 0) {
        colorClass = 'text-red-500';
        icon = <FaArrowDown />;
    } else if (percentValue === 0) {
        colorClass = 'text-yellow-500';
    }

    return (
        <div className={`rounded-lg`}>
            <h3 className="text-lg font-semibold">{title}</h3>
            <p className="mt-2 text-3xl font-bold">{value}</p>
            <p className="mt-1 text-sm">
                <span className={`mr-2 ${colorClass}`}>{icon}</span>
                <span className={colorClass}>{percentage}%</span>
            </p>
        </div>
    );
};

export default MetricCard;
