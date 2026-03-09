'use client';

import { useEffect, useState, useCallback, useMemo } from 'react';
import { useFormState } from '@app/store/jotai/form';
import { Input } from '@app/shadcn/components/ui/input';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@app/shadcn/components/ui/table';
import useFormFieldsAtom from '@app/store/jotai/fieldSelector';
import { cn } from '@app/shadcn/util/lib';
import { Close } from '@app/views/atoms/Icons/Close';
import { StandardFormFieldDto } from '@app/models/dtos/form';

interface TabularInputFieldProps {
  value: string[][];
  onChange: (value: string[][]) => void;
  rowTitles: string[];
  columnTitles: string[];
  disabled?: boolean;
  fieldId?: string;
  field: StandardFormFieldDto;
  isActiveField?: boolean;
  onDeleteRow?: (rowIndex: number) => void;
  onDeleteColumn?: (colIndex: number) => void;
}

export default function TabularInputField({
  value,
  onChange,
  rowTitles,
  columnTitles,
  disabled = false,
  field,
  onDeleteRow,
  onDeleteColumn
}: TabularInputFieldProps) {
  const { theme } = useFormState();
  const { activeField, updateTabularRowTitle, updateTabularColumnTitle } = useFormFieldsAtom();

  const minRows = 2;
  const minCols = 2;

  const columns = useMemo(() => 
    columnTitles?.length >= minCols ? columnTitles : Array(minCols).fill('').map((_, i) => `Col ${i + 1}`),
    [columnTitles]
  );

  const rows = useMemo(() => 
    rowTitles?.length >= minRows ? rowTitles : Array(minRows).fill('').map((_, i) => `Row ${i + 1}`), 
    [rowTitles]
  );

  const initialTableValue = useMemo(() => {
    if (value && value.length >= rows.length && value[0]?.length >= columns.length) return value;
    return rows.map(() => columns.map(() => ''));
  }, [value, rows.length, columns.length]);

  const [tableData, setTableData] = useState<string[][]>(initialTableValue);
  const [localRowTitles, setLocalRowTitles] = useState(rows);
  const [localColTitles, setLocalColTitles] = useState(columns);

  // Sync internal state with props
  useEffect(() => { setTableData(initialTableValue); }, [initialTableValue]);
  useEffect(() => { setLocalRowTitles(rows); }, [rows]);
  useEffect(() => { setLocalColTitles(columns); }, [columns]);

  const handleInputChange = useCallback((rowIdx: number, colIdx: number, val: string) => {
    const updated = tableData.map((row, r) =>
      row.map((cell, c) => (r === rowIdx && c === colIdx ? val : cell))
    );
    setTableData(updated);
    onChange(updated);
  }, [tableData, onChange]);

  const handleRowTitleChange = useCallback((rowIdx: number, val: string) => {
    const updated = [...localRowTitles];
    updated[rowIdx] = val;
    setLocalRowTitles(updated);
    updateTabularRowTitle(rowIdx, val);
  }, [localRowTitles, updateTabularRowTitle]);

  const handleColTitleChange = useCallback((colIdx: number, val: string) => {
    const updated = [...localColTitles];
    updated[colIdx] = val;
    setLocalColTitles(updated);
    updateTabularColumnTitle(colIdx, val);
  }, [localColTitles, updateTabularColumnTitle]);

  const sharedHeaderStyle = {
    background: (theme?.tertiary ?? '') + '55',
    borderColor: theme?.secondary,
    color: theme?.secondary,
  };

  return (
    <div className="w-full overflow-hidden rounded-lg shadow-sm">
      <div 
        className="overflow-x-auto rounded-lg border" 
        style={{ borderColor: theme?.secondary }}
      >
        <Table className="min-w-max w-full border-collapse">
          <TableHeader>
            <TableRow className="hover:bg-transparent">
              <TableHead
                className="sticky left-0 z-20 min-w-24 max-w-40 border-r border-b border-t-[2px] shadow-[2px_0_5px_-2px_rgba(0,0,0,0.1)]"
                style={sharedHeaderStyle}
              />
              {localColTitles.map((col, idx) => (
                <TableHead
                  key={idx}
                  className={cn(
                    "relative group text-center font-semibold px-3 py-3 min-w-28 max-w-48 border-r border-b border-t-[2px]",
                    idx === localColTitles.length - 1 && "rounded-tr-lg border-r-[2px]"
                  )}
                  style={sharedHeaderStyle}
                >
                  {disabled && activeField?.id === field.id && localColTitles.length > minCols && (
                    <div
                      className="absolute left-1 top-1 rounded-full bg-white p-1 opacity-50 h-5 w-5 cursor-pointer hover:opacity-100 z-10 flex items-center justify-center transition-opacity"
                      onClick={() => onDeleteColumn?.(idx)}
                    >
                      <Close className="h-3 w-3" />
                    </div>
                  )}
                  {disabled ? (
                    <Input
                      value={col ?? ''}
                      onChange={(e) => handleColTitleChange(idx, e.target.value)}
                      className="text-center font-semibold !text-sm bg-transparent border-none focus:ring-0 h-8"
                    />
                  ) : (
                    <span className="text-sm">{col}</span>
                  )}
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>

          <TableBody>
            {tableData.map((row, rowIdx) => (
              <TableRow key={rowIdx} className="hover:bg-muted/10 transition-colors">
                <TableCell
                  className={cn(
                    "sticky left-0 z-10 min-w-24 max-w-40 px-3 py-2 font-medium text-center border-r border-b shadow-[2px_0_5px_-2px_rgba(0,0,0,0.1)]",
                    rowIdx === tableData.length - 1 && "rounded-bl-lg border-b-[2px]"
                  )}
                  style={sharedHeaderStyle}
                >
                  {disabled && activeField?.id === field.id && tableData.length > minRows && (
                    <div
                      className="absolute left-1 top-1 rounded-full bg-white p-1 opacity-50 h-5 w-5 cursor-pointer hover:opacity-100 z-10 flex items-center justify-center transition-opacity"
                      onClick={() => onDeleteRow?.(rowIdx)}
                    >
                      <Close className="h-3 w-3" />
                    </div>
                  )}
                  {disabled ? (
                    <Input
                      value={localRowTitles[rowIdx] ?? ''}
                      onChange={(e) => handleRowTitleChange(rowIdx, e.target.value)}
                      className="text-center font-semibold !text-sm bg-transparent border-none focus:ring-0 h-8"
                    />
                  ) : (
                    <span className="text-sm">{localRowTitles[rowIdx]}</span>
                  )}
                </TableCell>

                {row.map((cell, colIdx) => (
                  <TableCell
                    key={colIdx}
                    className={cn(
                      "px-3 py-2 text-center border-r border-b",
                      rowIdx === tableData.length - 1 && colIdx === row.length - 1 && "rounded-br-lg border-b-[2px]",
                      colIdx === row.length - 1 && "border-r-[2px]"
                    )}
                    style={{
                      background: theme?.accent,
                      borderColor: theme?.secondary,
                      color: theme?.secondary
                    }}
                  >
                    <Input
                      value={cell ?? ''}
                      disabled={disabled}
                      onChange={(e) => handleInputChange(rowIdx, colIdx, e.target.value)}
                      className="text-center !text-sm bg-transparent border-none focus:ring-0 h-8"
                    />
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}