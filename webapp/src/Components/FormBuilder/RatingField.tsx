import { useState } from 'react';

import _ from 'lodash';

import { Star, StarBorder } from '@mui/icons-material';

interface IRatingFieldProps {
    field: any;
}

export default function RatingField({ field }: IRatingFieldProps) {
    const [hovered, setHovered] = useState(-1);

    return (
        <div
            className="flex gap-3 w-fit flex-wrap"
            onMouseLeave={() => {
                setHovered(-1);
            }}
        >
            {_.range(field.properties?.steps || 5).map((index) => {
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
