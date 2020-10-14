# vim:fileencoding=utf-8
# (c) 2020 Michał Górny <mgorny@gentoo.org>
# Released under the terms of the 2-clause BSD license.

import gzip
import hashlib
import os
import tempfile
import unittest

from importlib import util
from pathlib import Path

from ecleankernel.file import (KernelImage, ModuleDirectory,
                               UnrecognizedKernelError,
                               MissingDecompressorError)


def write_bzImage(path: Path,
                  version_line: bytes
                  ) -> None:
    """Write a pseudo-bzImage file at `path`, with `version_line`"""
    with open(path, 'wb') as f:
        f.write(0x202 * b'\0')
        f.write(b'HdrS')
        f.write(8 * b'\0')
        f.write(b'\x10\x00')
        f.write(version_line)


def write_raw(path: Path,
              version_line: bytes
              ) -> None:
    """Write a raw kernel binary at `path`, with `version_line`"""
    with open(path, 'wb') as f:
        f.write(0x210 * b'\0')
        f.write(version_line)


def write_compress(path: Path,
                   version_line: bytes
                   ) -> None:
    """Write a gzip compressed raw kernel binary at `path`,
    with `version_line`"""
    with gzip.open(path, 'wb') as f:
        # gzip would compress a string of 0s below 0x200,
        # so we fill in some incompressible gibberish
        s = b''
        for i in range(1, 0xff):
            m = hashlib.sha1()
            m.update(i.to_bytes(1, 'little'))
            s += m.digest()
        f.write(s)
        f.write(version_line)


class KernelImageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.td = tempfile.TemporaryDirectory()

    def tearDown(self) -> None:
        self.td.cleanup()

    def test_read_internal_version_bz(self) -> None:
        path = Path(self.td.name) / 'vmlinuz'
        write_bzImage(path, b'1.2.3 built on test')
        self.assertEqual(
            KernelImage(path).read_internal_version(),
            '1.2.3')

    def test_read_internal_version_raw(self) -> None:
        path = Path(self.td.name) / 'vmlinuz'
        write_raw(path, b'Linux version 1.2.3 built on test')
        self.assertEqual(
            KernelImage(path).read_internal_version(),
            '1.2.3')

    def test_read_internal_version_compress(self) -> None:
        path = Path(self.td.name) / 'vmlinuz'
        write_compress(path, b'Linux version 1.2.3 built on test')
        self.assertEqual(
            KernelImage(path).read_internal_version(),
            '1.2.3')

    def test_very_short(self) -> None:
        path = Path(self.td.name) / 'vmlinuz'
        with open(path, 'wb') as f:
            f.write(10 * b'\0')
        with self.assertRaises(UnrecognizedKernelError):
            KernelImage(path).read_internal_version()

    def test_bad_magic(self) -> None:
        path = Path(self.td.name) / 'vmlinuz'
        with open(path, 'wb') as f:
            f.write(0x210 * b'\0')
        with self.assertRaises(UnrecognizedKernelError):
            KernelImage(path).read_internal_version()

    def test_bad_file_magic(self) -> None:
        path = Path(self.td.name) / 'vmlinuz'
        with open(path, 'w') as f:
            f.write('Hello World')
        with self.assertRaises(UnrecognizedKernelError):
            KernelImage(path).read_internal_version()

    def test_missing_decompressor(self) -> None:
        if util.find_spec('lzo'):
            self.skipTest('the missing decompressor is installed')
        path = Path(self.td.name) / 'vmlinuz'
        with open(path, 'wb') as f:
            f.write(b'\x89\x4c\x5a\x4f\x00\x0d\x0a\x1a\x0a')
            f.write(0x210 * b'\0')
        with self.assertRaises(MissingDecompressorError):
            KernelImage(path).read_internal_version()

    def test_overflow_ver_string_bz(self) -> None:
        path = Path(self.td.name) / 'vmlinuz'
        path = Path(self.td.name) / 'vmlinuz'
        write_bzImage(path, b'1.2.3' + 0xffff * b'\0')
        with self.assertRaises(UnrecognizedKernelError):
            KernelImage(path).read_internal_version()

    def test_overflow_ver_string_raw(self) -> None:
        path = Path(self.td.name) / 'vmlinuz'
        write_raw(path, b'Linux version 1.2.3' + 0xffff * b'\0')
        with self.assertRaises(UnrecognizedKernelError):
            KernelImage(path).read_internal_version()

    def test_short(self) -> None:
        path = Path(self.td.name) / 'vmlinuz'
        with open(path, 'wb') as f:
            f.write(0x202 * b'\0')
            f.write(b'HdrS')
            f.write(8 * b'\0')
            f.write(b'\x10\x00')
        with self.assertRaises(UnrecognizedKernelError):
            KernelImage(path).read_internal_version()


class ModuleDirectoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.td = tempfile.TemporaryDirectory()

    def tearDown(self) -> None:
        self.td.cleanup()

    def test_abs_symlink(self) -> None:
        td = Path(self.td.name)
        mdir = td / 'modules/1.2.3'
        os.makedirs(mdir)
        os.makedirs(td / 'src/linux')
        os.symlink(td / 'src/linux', mdir / 'build')

        self.assertEqual(
            ModuleDirectory(mdir).get_build_dir(),
            td / 'src/linux')

    def test_rel_symlink(self) -> None:
        td = Path(self.td.name)
        mdir = td / 'modules/1.2.3'
        os.makedirs(mdir)
        os.makedirs(td / 'src/linux')
        os.symlink('../../src/linux', mdir / 'build')

        self.assertEqual(
            ModuleDirectory(mdir).get_build_dir(),
            mdir / '../../src/linux')
