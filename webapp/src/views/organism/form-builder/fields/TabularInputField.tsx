'use client';

import { useEffect, useState } from 'react';
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
  fieldId,
  field,
  isActiveField = false,
  onDeleteRow,
  onDeleteColumn
}: TabularInputFieldProps) {
  const { theme } = useFormState();
  const { updateRowTitle, updateColumnTitle, activeField, updateTabularRowTitle, updateTabularColumnTitle } = useFormFieldsAtom();

  const minRows = 2;
  const minCols = 2;

  const getDefaultArray = (len: number, fill: string) => Array(len).fill(fill);

  // Default column titles
  const columns =
    columnTitles && columnTitles.length >= minCols
      ? columnTitles
      : getDefaultArray(minCols, '').map((_, i) => `Col ${i + 1}`);

  // Default row titles
  const rows =
    rowTitles && rowTitles.length >= minRows
      ? rowTitles
      : getDefaultArray(minRows, '').map((_, i) => `Row ${i + 1}`);

  // Default value grid
  const defaultValue = getDefaultArray(rows.length, '').map(() =>
    getDefaultArray(columns.length, '')
  );
  const initialValue =
    value && value.length >= minRows && value[0]?.length >= minCols
      ? value
      : defaultValue;

  const [tableData, setTableData] = useState<string[][]>(initialValue);
  const [localRowTitles, setLocalRowTitles] = useState(rows);
  const [localColTitles, setLocalColTitles] = useState(columns);

  useEffect(() => {
    if ((!value || value.length === 0) && initialValue.length > 0) {
      onChange(initialValue);
    }
  }, []);

  useEffect(() => {
    if (
      value &&
      value.length >= minRows &&
      value[0]?.length >= minCols
    ) {
      setTableData(value);
    } else {
      setTableData(defaultValue);
    }
  }, [value, columns.length, rows.length]);

  useEffect(() => {
    setLocalRowTitles(rows);
  }, [rowTitles, rows.length]);

  useEffect(() => {
    setLocalColTitles(columns);
  }, [columnTitles, columns.length]);

  const handleInputChange = (
    rowIdx: number,
    colIdx: number,
    val: string
  ) => {
    const updated = tableData.map((row, r) =>
      row.map((cell, c) => (r === rowIdx && c === colIdx ? val : cell))
    );
    setTableData(updated);
    onChange(updated);
  };

  const handleRowTitleChange = (rowIdx: number, val: string) => {
    const updated = [...localRowTitles];
    updated[rowIdx] = val;
    setLocalRowTitles(updated);
    updateTabularRowTitle(rowIdx, val);
  };

  const handleColTitleChange = (colIdx: number, val: string) => {
    const updated = [...localColTitles];
    updated[colIdx] = val;
    setLocalColTitles(updated);
    updateTabularColumnTitle(colIdx, val);
  };

  return (
  <div className="w-full overflow-x-auto rounded-lg shadow-sm p-1">
      <div
        className="overflow-hidden rounded-lg border mb-2 text-sm text-foreground"
        style={{ borderColor: theme?.secondary }}
      >
        <Table className="min-w-max w-full border-collapse">
          <TableHeader>
            <TableRow className="hover:bg-transparent">
              {/* Top-left corner empty cell */}
              <TableHead
                className="sticky left-0 z-10 min-w-24 max-w-40 px-3 py-3 font-semibold rounded-tl-lg border-r border-b border-l-0 border-t-[2px]"
                style={{
                  background: (theme?.tertiary ?? '') + '55',
                  borderColor: theme?.secondary,
                  color: theme?.secondary
                }}
              />

              {localColTitles.map((col, idx) => (
                <TableHead
                  key={idx}
                  className={cn(
                    "relative group text-center font-semibold px-3 py-3 whitespace-nowrap min-w-28 max-w-48 border-r border-b border-t-[2px] border-l-0",
                    idx === localColTitles.length - 1 && "rounded-tr-lg border-r-[2px]"
                  )}
                  style={{
                    background: (theme?.tertiary ?? '') + '55',
                    borderColor: theme?.secondary,
                    color: theme?.secondary
                  }}
                >
                  {disabled && activeField?.id && localColTitles.length > 2 && (
                    <div
                      className="cross-top absolute left-1 top-1 rounded-full bg-white p-1 opacity-50 h-6 w-6 cursor-pointer hover:opacity-100 z-10"
                      onClick={() => onDeleteColumn?.(idx)}
                    >
                      <Close className="h-4 w-4" />
                    </div>
                  )}
                  {disabled ? (
                    <Input
                      value={col ?? ''}
                      onChange={(e) => handleColTitleChange(idx, e.target.value)}
                      className="text-center font-semibold !text-sm bg-transparent border-none outline-none focus:ring-0"
                      style={{ color: theme?.secondary }}
                    />
                  ) : (
                    <span>{col}</span>
                  )}
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>

          <TableBody>
            {tableData.map((row, rowIdx) => (
              <TableRow key={rowIdx} className="hover:bg-muted/30">
                {/* Row header cell */}
                <TableCell
                  className={cn(
                    "relative group sticky left-0 z-10 min-w-24 max-w-40 px-3 py-2 font-medium text-center border-r border-b border-t-0 border-l-[2px]",
                    rowIdx === tableData.length - 1 && "rounded-bl-lg border-b-[2px]"
                  )}
                  style={{
                    background: (theme?.tertiary ?? '') + '55',
                    borderColor: theme?.secondary,
                    color: theme?.secondary
                  }}
                >
                  {disabled && activeField?.id && tableData.length > 2 && (
                    <div
                      className="cross-top absolute left-1 top-1 rounded-full bg-white p-1 opacity-50 h-6 w-6 cursor-pointer hover:opacity-100 z-10"
                      onClick={() => onDeleteRow?.(rowIdx)}
                    >
                      <Close className="h-4 w-4" />
                    </div>
                  )}
                  {disabled ? (
                    <Input
                      value={localRowTitles[rowIdx] ?? ''}
                      onChange={(e) => handleRowTitleChange(rowIdx, e.target.value)}
                      className="text-center font-semibold !text-sm bg-transparent border-none outline-none focus:ring-0"
                      style={{ color: theme?.secondary }}
                    />
                  ) : (
                    <span>{localRowTitles[rowIdx]}</span>
                  )}
                </TableCell>

                {/* Data cells */}
                {row.map((cell, colIdx) => (
                  <TableCell
                    key={colIdx}
                    className={cn(
                      "px-3 py-2 text-center font-medium border-r border-b border-t-0 border-l-0",
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
                      className="text-center !text-sm bg-transparent border-none outline-none focus:ring-0"
                      style={{ color: theme?.secondary }}
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