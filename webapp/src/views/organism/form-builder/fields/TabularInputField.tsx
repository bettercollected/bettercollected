'use client';

import React, { useEffect, useState } from 'react';
import { useFormState } from '@app/store/jotai/form';
import { Input } from '@app/shadcn/components/ui/input';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@app/shadcn/components/ui/table';
import useFormFieldsAtom from '@app/store/jotai/fieldSelector';
import { cn } from '@app/shadcn/util/lib';
import { Close } from '@app/views/atoms/Icons/Close';

interface TabularInputFieldProps {
  value: string[][];
  onChange: (value: string[][]) => void;
  rowTitles: string[];
  columnTitles: string[];
  disabled?: boolean;
  fieldId?: string;
}

export default function TabularInputField({
  value,
  onChange,
  rowTitles,
  columnTitles,
  disabled = false,
  fieldId
}: TabularInputFieldProps) {
  const { theme } = useFormState();
  const { updateRowTitle, updateColumnTitle, activeField } = useFormFieldsAtom();

  const minRows = 3;
  const minCols = 3;

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
    if (activeField?.id === fieldId) updateRowTitle(rowIdx, val);
  };

  const handleColTitleChange = (colIdx: number, val: string) => {
    const updated = [...localColTitles];
    updated[colIdx] = val;
    setLocalColTitles(updated);
    if (activeField?.id === fieldId) updateColumnTitle(colIdx, val);
  };

  return (
  <div className="w-full overflow-x-auto rounded-lg shadow-sm p-1">
    <div
      className="overflow-hidden rounded-lg border mb-2 text-sm text-foreground"
      style={{ borderColor: theme?.secondary }}
    >
      <Table className="min-w-max w-full border-collapse">
        <TableHeader>
          <TableRow className="bg-muted/50 hover:bg-muted/50">
            {/* Top-left corner cell */}
            <TableHead
              className="sticky left-0 z-10 min-w-24 max-w-40 px-3 py-3 font-semibold text-foreground bg-muted/50 rounded-tl-lg border-r border-b border-l-0 bg-opacity-20"
              style={{ background: theme?.accent, borderColor: theme?.secondary }}
            >
            </TableHead>

            {localColTitles.map((col, idx) => (
              <TableHead
                key={idx}
                className={cn(
                  "relative text-center font-semibold text-foreground px-3 py-3 whitespace-nowrap min-w-28 max-w-48 border-r border-b border-t-0 border-l-0",
                  idx === localColTitles.length - 1 && "rounded-tr-lg",
                )}
                style={{ color: theme?.secondary, borderColor: theme?.secondary }}
              >
                {disabled ? (
                  col
                ) : (
                  <Input
                    value={col ?? ''}
                    disabled={disabled}
                    onChange={(e) => handleColTitleChange(idx, e.target.value)}
                    className={cn("text-center font-semibold !text-sm")}
                    style={{
                      borderColor: theme?.tertiary,
                      color: theme?.secondary,
                      background: theme?.accent,
                    }}
                  />
                )}

                {disabled && activeField?.id === fieldId && (
                  <div
                      className="cross-left absolute top-1 rounded-full bg-white p-1 opacity-50"
                      onClick={() => {
                          deleteTabularColumn();
                      }}
                  >
                      <Close className="h-4 w-4" />
                  </div>
                )}
              </TableHead>
            ))}
          </TableRow>
        </TableHeader>

        <TableBody>
          {tableData.map((row, rowIdx) => (
            <TableRow key={rowIdx} className="hover:bg-muted/30">
              <TableCell
                className={cn(
                  "sticky left-0 z-10 min-w-24 max-w-40 px-3 py-2 font-medium text-center text-foreground bg-muted/50 border-r border-b border-t-0 border-l",
                  rowIdx === tableData.length - 1 && "rounded-bl-lg"
                )}
                style={{ color: theme?.secondary, background: theme?.accent, borderColor: theme?.secondary }}
              >
                {disabled ? (
                  localRowTitles[rowIdx]
                ) : (
                  <Input
                    value={localRowTitles[rowIdx] ?? ''}
                    disabled={disabled}
                    onChange={(e) => handleRowTitleChange(rowIdx, e.target.value)}
                    className={cn("text-center font-semibold !text-sm")}
                    style={{
                      borderColor: theme?.tertiary,
                      color: theme?.secondary,
                      background: theme?.accent,
                    }}
                  />
                )}
                {disabled && activeField?.id === fieldId && (field?.properties?.fields?.length || -1) > 1 && (
                  <div
                      className="cross-top absolute left-1 rounded-full bg-white p-1 opacity-50"
                      onClick={() => {
                          deleteRow(index);
                      }}
                  >
                      <Close className="h-4 w-4" />
                  </div>
                )}
              </TableCell>

              {row.map((cell, colIdx) => (
                <TableCell
                  key={colIdx}
                  className={cn(
                    "px-3 py-2 text-center font-medium text-foreground bg-muted/50 border-r border-b border-t-0 border-l-0",
                    rowIdx === tableData.length - 1 &&
                      colIdx === row.length - 1 &&
                      "rounded-br-lg"
                  )}
                  style={{ color: theme?.secondary, background: theme?.accent, borderColor: theme?.secondary }}
                >
                  <Input
                    value={cell ?? ''}
                    disabled={disabled}
                    onChange={(e) => handleInputChange(rowIdx, colIdx, e.target.value)}
                    className={cn("text-center !text-sm", disabled && "bg-muted")}
                    style={{
                      borderColor: theme?.tertiary,
                      color: theme?.secondary,
                      background: theme?.accent,
                    }}
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