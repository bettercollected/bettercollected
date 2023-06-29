import CheckBoxOutlineBlankIcon from '@mui/icons-material/CheckBoxOutlineBlank';
import RadioButtonUncheckedIcon from '@mui/icons-material/RadioButtonUnchecked';

interface IMatrixFieldProps {
    allowMultipleSelection: boolean;
    rows: Array<any>;
    columns: Array<any>;
}

export default function MatrixField({ allowMultipleSelection, rows, columns }: IMatrixFieldProps) {
    if (rows.length === 0) rows = [1];
    if (columns.length === 0) columns = [1];
    return (
        <div className="overflow-auto">
            <div className={`grid grid-flow-col grid-cols-${columns.length + 1}`}>
                <div className="border w-40">
                    <div className="h-1 w-1 border" />
                </div>
                {columns.map((column, index) => (
                    <input key={index} placeholder={'Column ' + (index + 1)} className="border w-40 text-center outline-none p-2" />
                ))}
            </div>
            {rows.map((row, index) => (
                <div key={index} className={`grid grid-flow-col grid-cols-${columns.length + 1}`}>
                    <input className="border outline-none p-2 w-40" placeholder={`Row ` + (index + 1)} />
                    {columns.map((a, index) => {
                        const Component = allowMultipleSelection ? CheckBoxOutlineBlankIcon : RadioButtonUncheckedIcon;
                        return (
                            <div key={index} className="border flex items-center justify-center p-2 w-40">
                                <Component className="text-gray-400" />
                            </div>
                        );
                    })}
                </div>
            ))}
        </div>
    );
}
