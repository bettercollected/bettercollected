import React, { useState, useEffect, useRef } from 'react';

const timeRanges = ['Today', 'Last 24 hours', 'This week', 'Last 7 days', 'This month', 'Last 30 days', 'Last 90 days', 'This year', 'Last 6 months', 'Last 12 months', 'All time'];

interface TimeRangeSelectorProps {
    onRangeSelect: (range: string) => void;
}

const TimeRangeSelector: React.FC<TimeRangeSelectorProps> = ({ onRangeSelect }) => {
    const [selectedRange, setSelectedRange] = useState<string>('Last 24 hours');
    const [isOpen, setIsOpen] = useState<boolean>(false);
    const dropdownRef = useRef<HTMLDivElement>(null);

    const handleRangeChange = (range: string) => {
        setSelectedRange(range);
        onRangeSelect(range);
        setIsOpen(false);
    };

    const toggleDropdown = () => {
        setIsOpen(!isOpen);
    };

    const handleClickOutside = (event: MouseEvent) => {
        if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
            setIsOpen(false);
        }
    };

    useEffect(() => {
        if (isOpen) {
            document.addEventListener('mousedown', handleClickOutside);
        } else {
            document.removeEventListener('mousedown', handleClickOutside);
        }

        return () => {
            document.removeEventListener('mousedown', handleClickOutside);
        };
    }, [isOpen]);

    return (
        <div ref={dropdownRef} className="relative inline-block py-4 text-left">
            <button type="button" onClick={toggleDropdown} className="inline-flex w-full justify-between rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 shadow-sm hover:bg-gray-50 focus:outline-none">
                {selectedRange}
                <svg className="-mr-1 ml-2 h-5 w-5" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
                    <path fillRule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" clipRule="evenodd" />
                </svg>
            </button>
            {isOpen && (
                <div className="left-0.1 absolute mt-2 w-56 origin-top-right rounded-md bg-white shadow-lg ring-1 ring-black ring-opacity-5">
                    <div className="py-1">
                        {timeRanges.map((range, index) => (
                            <button
                                key={index}
                                onClick={() => handleRangeChange(range)}
                                className={`block w-full px-4 py-2 text-left text-sm ${selectedRange === range ? 'bg-gray-100 text-gray-900' : 'text-gray-700'} hover:bg-gray-100 hover:text-gray-900`}
                            >
                                {range}
                            </button>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
};

export default TimeRangeSelector;
