#!/usr/bin/env python3
"""Read pinned OpenModelica MAT-v4 results without omc or third-party packages.

This adapter serializes recorded values; it does not solve equations, evaluate
parameters, interpolate, or resample. It supports numeric Atrajectory 1.1 files
with binTrans/binNormal storage, IEEE little/big endian, and constant data_1
parameters. Other formats fail explicitly. The CSV includes parameters and
signed aliases that OpenModelica's direct simulation CSV writer omits.

Format: https://github.com/OpenModelica/OpenModelica/blob/v1.27.1/doc/UsersGuide/source/technical_details.rst
Native reader semantics: https://github.com/OpenModelica/OpenModelica/blob/v1.27.1/OMCompiler/Compiler/runtime/SimulationResults.c
"""
from __future__ import annotations

import argparse
from array import array
import csv
from dataclasses import dataclass
import math
from pathlib import Path
import struct
import sys


class NativeMatError(ValueError):
    """Unsupported or inconsistent native result file."""


@dataclass
class _Matrix:
    rows: int
    cols: int
    kind: int
    precision: int
    values: array

    def row(self, index):
        return self.values[index::self.rows]

    def column(self, index):
        return self.values[index * self.rows:(index + 1) * self.rows]


def _text(values):
    raw = bytes(values)
    head, _, padding = raw.partition(b"\0")
    if padding.strip(b"\0 "):
        raise NativeMatError("Non-padding bytes after a string terminator")
    try:
        return head.rstrip(b" ").decode("utf-8")
    except UnicodeDecodeError as error:
        raise NativeMatError("Invalid UTF-8 in native text") from error


def _read_matrices(path):
    content = Path(path).read_bytes()
    if len(content) < 20:
        raise NativeMatError("Truncated MAT-v4 header")
    # MOPT's machine digit is 0 for IEEE little endian and 1 for IEEE big endian.
    little, big = struct.unpack_from("<i", content)[0], struct.unpack_from(">i", content)[0]
    if 0 <= little < 1000:
        endian, machine = "<", 0
    elif 1000 <= big < 2000:
        endian, machine = ">", 1
    else:
        raise NativeMatError("Unsupported MAT-v4 byte order or machine format")
    formats = {0: ("d", 8), 1: ("f", 4), 2: ("i", 4),
               3: ("h", 2), 4: ("H", 2), 5: ("B", 1)}
    matrices, offset = {}, 0
    while offset < len(content):
        if len(content) - offset < 20:
            raise NativeMatError("Truncated MAT-v4 matrix header")
        mopt, rows, cols, imaginary, name_size = struct.unpack_from(endian + "5i", content, offset)
        offset += 20
        precision, kind = (mopt // 10) % 10, mopt % 10
        if (mopt < 0 or mopt // 1000 != machine or (mopt // 100) % 10 != 0
                or precision not in formats or kind not in (0, 1) or imaginary != 0):
            raise NativeMatError("Unsupported MAT-v4 numeric, sparse or complex matrix")
        if rows < 1 or cols < 1 or name_size < 2 or name_size > 128:
            raise NativeMatError("Invalid MAT-v4 matrix dimensions or name length")
        code, size = formats[precision]
        end = offset + name_size + rows * cols * size
        if end > len(content):
            raise NativeMatError("Truncated MAT-v4 matrix payload")
        encoded_name = content[offset:offset + name_size]
        if encoded_name[-1:] != b"\0" or b"\0" in encoded_name[:-1]:
            raise NativeMatError("Invalid MAT-v4 matrix name")
        try:
            name = encoded_name[:-1].decode("ascii")
        except UnicodeDecodeError as error:
            raise NativeMatError("Non-ASCII MAT-v4 matrix name") from error
        if name in matrices:
            raise NativeMatError("Duplicate MAT-v4 matrix: " + name)
        if kind == 1 and precision != 5:
            raise NativeMatError("Native text matrices must contain bytes")
        values = array(code)
        if values.itemsize != size:
            raise NativeMatError("Unsupported host numeric representation")
        values.frombytes(content[offset + name_size:end])
        if size > 1 and ((endian == "<") != (sys.byteorder == "little")):
            values.byteswap()
        if precision in (0, 1) and not all(math.isfinite(value) for value in values):
            raise NativeMatError("Nonfinite native result value in " + name)
        matrices[name] = _Matrix(rows, cols, kind, precision, values)
        offset = end
    required = {"Aclass", "name", "description", "dataInfo", "data_1", "data_2"}
    if set(matrices) != required:
        raise NativeMatError("Expected exactly the six native Atrajectory matrices")
    return matrices


class NativeMatResult:
    """A complete native recording with exact sampled columns and parameters.

    ``names`` is time first followed by sorted native names, matching the
    existing omc-based exporter inventory. ``times`` retains duplicate samples.
    ``column(name)`` always returns a fresh list of floats.
    """

    def __init__(self, path):
        self.path = Path(path)
        matrices = _read_matrices(self.path)
        aclass = matrices["Aclass"]
        if aclass.kind != 1 or aclass.rows != 4:
            raise NativeMatError("Invalid Aclass text matrix")
        identity = [_text(aclass.row(i)) for i in range(4)]
        if identity[:3] != ["Atrajectory", "1.1", ""] or identity[3] not in ("binTrans", "binNormal"):
            raise NativeMatError("Unsupported Atrajectory identity, version or storage")
        self.storage = identity[3]
        self._transposed = self.storage == "binTrans"
        names, descriptions, info = (matrices[k] for k in ("name", "description", "dataInfo"))
        if names.kind != 1 or descriptions.kind != 1 or info.kind != 0 or info.precision != 2:
            raise NativeMatError("Invalid name, description or dataInfo matrix type")
        n = names.cols if self._transposed else names.rows
        if ((descriptions.cols if self._transposed else descriptions.rows) != n
                or (info.rows, info.cols) != ((4, n) if self._transposed else (n, 4))):
            raise NativeMatError("Native name and dataInfo dimensions disagree")
        native_names = [_text(names.column(i) if self._transposed else names.row(i)) for i in range(n)]
        if any(not name for name in native_names) or len(set(native_names)) != n or "time" not in native_names:
            raise NativeMatError("Empty, duplicate or missing time variable name")
        self._data1, self._data2 = matrices["data_1"], matrices["data_2"]
        for matrix in (self._data1, self._data2):
            if matrix.kind != 0 or matrix.precision not in (0, 1):
                raise NativeMatError("Native data matrices must contain real floating-point values")
        self._nparam = self._data1.rows if self._transposed else self._data1.cols
        self._nvar = self._data2.rows if self._transposed else self._data2.cols
        self._param_points = self._data1.cols if self._transposed else self._data1.rows
        if self._param_points not in (1, 2):
            raise NativeMatError("Unsupported data_1 time layout")
        self._info = {}
        for i, name in enumerate(native_names):
            channel, index, interpolation, extrapolation = info.column(i) if self._transposed else info.row(i)
            limit = 1 if channel == 0 else self._nparam if channel == 1 else self._nvar
            if (channel not in (0, 1, 2) or index == 0 or abs(index) > limit
                    or interpolation != 0 or extrapolation not in (-1, 0, 1)):
                raise NativeMatError("Invalid native dataInfo entry for " + name)
            self._info[name] = (channel, index)
        if self._info["time"] != (0, 1):
            raise NativeMatError("The time variable must reference the native abscissa")
        self.times = self._series(self._data2, 0)
        if (len(self.times) < 2 or self.times[-1] <= self.times[0]
                or any(b < a for a, b in zip(self.times, self.times[1:]))):
            raise NativeMatError("Native timestamps must be nondecreasing and span an interval")
        parameter_time = self._series(self._data1, 0)
        if parameter_time[0] != self.times[0] or (len(parameter_time) == 2 and parameter_time[1] != self.times[-1]):
            raise NativeMatError("Native parameter and trajectory time intervals disagree")
        for i in range(1, self._nparam):
            values = self._series(self._data1, i)
            if any(value != values[0] for value in values[1:]):
                raise NativeMatError("Time-varying data_1 parameters are unsupported")
        self.names = ["time", *sorted(name for name in native_names if name != "time")]

    def _series(self, matrix, index):
        values = matrix.row(index) if self._transposed else matrix.column(index)
        return [float(value) for value in values]

    def column(self, name):
        if name not in self._info:
            raise KeyError("Native result variable not found: " + name)
        channel, index = self._info[name]
        if channel == 0:
            values = list(self.times)
        elif channel == 1:
            values = [self._series(self._data1, abs(index) - 1)[0]] * len(self.times)
        else:
            values = self._series(self._data2, abs(index) - 1)
        return [-value for value in values] if index < 0 else values

    def write_csv(self, path):
        path = Path(path)
        columns = [self.column(name) for name in self.names]
        temporary = path.with_name(path.name + ".tmp")
        try:
            with temporary.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.writer(stream)
                writer.writerow(self.names)
                writer.writerows(zip(*columns))
            temporary.replace(path)
        finally:
            if temporary.exists():
                temporary.unlink()
        return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = NativeMatResult(args.input)
    result.write_csv(args.output)
    print(f"PASS native MAT to CSV without omc: {len(result.times)} original samples, {len(result.names)} columns")


if __name__ == "__main__":
    main()
