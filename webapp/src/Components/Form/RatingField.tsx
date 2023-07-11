import { useState } from 'react';

import _ from 'lodash';

import { Star, StarBorder } from '@mui/icons-material';

import { StandardFormQuestionDto } from '@app/models/dtos/form';
import { addAnswer, selectAnswer, selectAnswers } from '@app/store/fill-form/slice';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';

export default function RatingField({ field }: { field: StandardFormQuestionDto }) {
    const dispatch = useAppDispatch();
    const [hovered, setHovered] = useState(-1);
    const answer = useAppSelector(selectAnswer(field.id));
    return (
        <div className="w-fit mt-3">
            {_.range(field.properties?.steps || 5).map((index) => {
                const Component = index <= hovered ? Star : StarBorder;

                return (
                    <span
                        key={index}
                        onMouseOut={() => {
                            setHovered((answer?.number || 0) - 1 || -1);
                        }}
                        onClick={() => {
                            const answer: any = {
                                field: {
                                    id: field.id
                                }
                            };
                            answer.number = index + 1;
                            dispatch(addAnswer(answer));
                        }}
                        onMouseOver={() => {
                            setHovered(index);
                        }}
                    >
                        <Component fontSize="large" className={`pointer-events-none ${index <= hovered ? 'cursor-pointer text-yellow-500' : 'text-gray-400'} `} />
                    </span>
                );
            })}
        </div>
    );
}
