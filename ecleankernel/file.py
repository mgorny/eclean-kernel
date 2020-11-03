# vim:fileencoding=utf-8
# (c) 2011-2020 Michał Górny <mgorny@gentoo.org>
# Released under the terms of the 2-clause BSD license.

import enum
import errno
import importlib
import os
import shutil
import struct

from pathlib import Path


@enum.unique
class KernelFileType(enum.Enum):
    KERNEL = 'vmlinuz'
    SYSTEM_MAP = 'systemmap'
    CONFIG = 'config'
    INITRAMFS = 'initramfs'
    MODULES = 'modules'
    BUILD = 'build'
    MISC = 'misc'
    EMPTYDIR = 'emptydir'


class UnrecognizedKernelError(Exception):
    pass


class MissingDecompressorError(Exception):
    pass


class GenericFile(object):
    """A generic file associated with a kernel"""

    path: Path
    ftype: KernelFileType

    def __init__(self,
                 path: Path,
                 ftype: KernelFileType
                 ) -> None:
        self.path = path
        self.ftype = ftype

    def remove(self) -> bool:
        """
        Remove this file

        Call an appropriate removal function for this file.  Return True
        if it was successfully removed, False if it was kept.  Raise
        FileNotFoundError if it were not found (which is fine).
        """
        os.unlink(self.path)
        return True

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, GenericFile):
            return NotImplemented
        return self.path == other.path and self.ftype == other.ftype

    def __repr__(self) -> str:
        return (f'GenericFile({repr(self.path)}, '
                f'KernelFileType.{repr(self.ftype.name)})')


class GenericDirectory(GenericFile):
    """A subclass of `GenericFile` for directories"""

    def remove(self) -> bool:
        """
        Remove this file

        Call an appropriate removal function for this file.  Return True
        if it was successfully removed, False if it was kept.  Raise
        FileNotFoundError if it were not found (which is fine).
        """
        shutil.rmtree(self.path)
        return True

    def __repr__(self) -> str:
        return (f'GenericDirectory({repr(self.path)}, '
                f'KernelFileType.{repr(self.ftype.name)})')


class KernelImage(GenericFile):
    """A recognized kernel image"""

    internal_version: str

    def __init__(self,
                 path: Path
                 ) -> None:
        super().__init__(path, KernelFileType.KERNEL)
        self.internal_version = self.read_internal_version()

    def decompress_raw(self) -> bytes:
        f = open(self.path, 'rb')
        magic_dict = {
            b'\x1f\x8b\x08': 'gzip',
            b'\x42\x5a\x68': 'bz2',
            b'\xfd\x37\x7a\x58\x5a\x00': 'lzma',
            b'\x5d\x00\x00': 'lzma',
            b'\x04\x22\x4d\x18': 'lz4.frame',
            b'\x28\xb5\x2f\xfd': 'zstandard',
            b'\x89\x4c\x5a\x4f\x00\x0d\x0a\x1a\x0a': 'lzo',
            }
        maxlen = max(len(x) for x in magic_dict)
        header = f.read(maxlen)
        f.seek(0)
        for magic, comp in magic_dict.items():
            if header.startswith(magic):
                try:
                    mod = importlib.import_module(comp)
                except ModuleNotFoundError:
                    raise MissingDecompressorError(
                        f'Kernel file {self.path} is compressed with '
                        f'{comp}, but the required decompressor '
                        f'is not installed')
                if comp == 'zstandard':
                    # Technically a redundant import, this is just
                    # to make your IDE happy :)
                    import zstandard
                    reader = zstandard.ZstdDecompressor().stream_reader(f)
                    decomp = b''
                    while True:
                        chunk = reader.read(1024*1024)
                        decomp += chunk
                        if not chunk:
                            break
                        return decomp
                else:
                    return getattr(mod, 'decompress')(f.read())
        return f.read()

    def read_internal_version(self) -> str:
        """Read version from the kernel file"""
        f = open(self.path, 'rb')
        f.seek(0x200)
        # short seek would result in eof, so read() will return ''
        buf = f.read(0x10)
        if len(buf) != 0x10:
            raise UnrecognizedKernelError(
                f'Kernel file {self.path} terminates before bzImage '
                f'header')
        if buf[2:6] == b'HdrS':
            offset = struct.unpack_from('H', buf, 0x0e)[0]
            f.seek(offset - 0x10, 1)
            buf = f.read(0x100)  # XXX
            if not buf:
                raise UnrecognizedKernelError(
                    f'Kernel file {self.path} terminates before expected '
                    f'version string position ({offset + 0x200})')
            ret = buf.split(b' ', 1)
        else:
            # If it's not a bzImage it must be a raw binary,
            # check if it's compressed first
            b = self.decompress_raw()
            # unlike with bzImage, the raw kernel binary has no header
            # that includes the version, so we parse the version message
            # that appears on boot
            ver_start = 'Linux version '
            pos = b.find(ver_start.encode())
            if pos == -1:
                raise UnrecognizedKernelError(
                    f'Kernel file {self.path} does not appear '
                    f'to have a version string, '
                    f'or the compression format was not recognized')
            pos += len(ver_start)
            sbuf = b[pos:pos + 0x100]
            ret = sbuf.split(b' ', 1)
        if len(ret) == 1:
            raise UnrecognizedKernelError(
                f'Kernel file {self.path} terminates '
                f'before end of version string')
        return ret[0].decode()

    def __repr__(self) -> str:
        return (f'KernelImage({repr(self.path)})')


class ModuleDirectory(GenericDirectory):
    """A kernel module collection directory"""

    def __init__(self,
                 path: Path
                 ) -> None:
        super().__init__(path, KernelFileType.MODULES)

    def get_build_dir(self) -> Path:
        return self.path / os.readlink(self.path / 'build')

    def __repr__(self) -> str:
        return (f'ModuleDirectory({repr(self.path)})')


class EmptyDirectory(GenericFile):
    """A parent directory that is removed if it is empty"""

    def __init__(self,
                 path: Path
                 ) -> None:
        super().__init__(path, KernelFileType.EMPTYDIR)

    def remove(self) -> bool:
        try:
            os.rmdir(self.path)
        except OSError as e:
            if e.errno in (errno.EEXIST, errno.ENOTEMPTY):
                return False
            raise
        return True

    def __repr__(self) -> str:
        return (f'EmptyDirectory({repr(self.path)})')
