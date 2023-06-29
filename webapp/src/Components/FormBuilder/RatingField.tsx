import { useState } from 'react';

import _ from 'lodash';

import { Star, StarBorder } from '@mui/icons-material';

interface IRatingFieldProps {
    number: number;
}

export default function RatingField({ number }: IRatingFieldProps) {
    const [hovered, setHovered] = useState(-1);

    return (
        <div
            className="flex gap-3 w-fit flex-wrap"
            onMouseLeave={() => {
                setHovered(-1);
            }}
        >
            {_.range(number).map((index) => {
                const Component = index <= hovered ? Star : StarBorder;

                return (
                    <Component
                        fontSize="large"
                        key={index}
                        onMouseEnter={() => {
                            setHovered(index);
                        }}
                        className={`${index <= hovered ? 'cursor-pointer text-yellow-500' : 'text-gray-400'} `}
                    />
                );
            })}
        </div>
    );
}
