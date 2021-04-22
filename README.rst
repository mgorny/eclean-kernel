eclean-kernel
=============

Introduction
------------

*eclean-kernel* is a small tool aimed at removing old and stale kernel files. It
does not only remove old kernels itself but also tries to remove all related
files including auxiliary files in /boot, kernel modules and even the source
tree.


Steps to use :
----------------

git clone https://github.com/mgorny/eclean-kernel.git

cd eclean-kernel (Change dir to eclean-kernel)

pip install .  (To install 'setup.py' file)

Commands usage in eclean-kernel::

	eclean-kernel -n 3 -p

where ``-n 3`` is used to keep three newest kernels around, and ``-p`` makes
eclean-kernel only print kernels which would be removed.

In case the results are satisfactory, use::

	eclean-kernel -n 3

to actually remove the kernels.

If you are unsure whether kernel files are mapped correctly, you can use
list mode::

	eclean-kernel -l

which just lists found kernels with file mappings.


Configuration file
------------------

Some default options can be specified in ``eclean-kernel.rc`` file in a location
mandated by the XDG configuration directory setting, e.g. ``~/.config/``.

The file format is very simple -- additional command-line options are specified
in shell style. For example, to keep three newest kernels and always preserve
kernel configs, ``~/.config/eclean-kernel.rc`` would contain::

	-n 3 -x config

The options read from config files will be parsed before actual command-line
options, so the latter will override them.


Fiding and mapping kernels
--------------------------

eclean-kernel supports two distinct /boot layouts: the bootloader spec
layout (gummiboot / systemd-boot) and the legacy /boot layout.
The former is used if ``/boot/MACHINE-ID`` or ``/boot/EFI/MACHINE-ID``
are found, otherwise the latter is used.

The bootloader spec layout uses subdirectories of ``/boot/MACHINE-ID``
named after kernel versions. It expects the kernel to be named
``linux``, and initramfs to be named ``initrd``. However, it collects
arbitrary files in that directory as well.

The legacy layout scans all files directly in ``/boot`` directory
that are named as ``PREFIX-VERSION``. Files recognized as bzImages
can have any prefix, other files use a predefined list of prefixes.

In both layouts, eclean-kernel looks for kernel modules
in ``/lib/modules/REALVERSION`` where *REALVERSION* corresponds to
the actual kernel version string used by the kernel itself. It is read
from kernel image and it is assumed to be equal to *VERSION* for libdirs
unmatched to any kernel image.

In other words, genkernel-generated ``kernel-genkernel-ARCH-X.Y.Z`` will
match ``System.map-genkernel-ARCH-X.Y.Z`` and ``/lib/modules/X.Y.Z``.


Choosing kernels to remove
--------------------------

The kernel choice algorithm is quite simple:

1. If the kernel is currently used, don't remove it;
2. If the kernel is referenced by a bootloader, don't remove it
   (unless ``--destructive``);
3. If auxiliary files do not map to existing kernel, remove them;
4. If ``--all`` is used, remove the kernel;
5. If kernel is not within *N* newest kernels (where *N* is the argument
   to ``-n``), remove it.

The program always derefences symlinks and counts real path references. Thus,
a particular file will be removed only if all kernels referencing it are removed
as well. This is especially important for shared kernel sources.


Bootloader support
------------------

In order to determine kernels currently used, eclean-kernel is supposed to read
configuration files used by the bootloader. Right now, the following bootloaders
are supported (and looked up in the following order):

1. lilo,
2. grub2,
3. grub,
4. yaboot.

There is also a pseudo-bootloader module called *symlinks* which assumes files
symlinked to ``/boot/PREFIX`` and ``/boot/PREFIX.old`` are used.

By default, eclean-kernel uses the first bootloader from the above list for
which a configuration file exists, and uses *symlinks* as a fallback. This can
be changed using ``--bootloader`` argument.


Reporting bugs
--------------

Please report bugs either to `the issue tracker`_ or `Gentoo Bugzilla`_. When
reporting a bug, please attach the outputs of::

	eclean-kernel -l
	ls -l /boot /lib/modules/*

If relevant, please attach bootloader configuration files as well.

.. _the issue tracker: https://github.com/mgorny/eclean-kernel/issues
.. _Gentoo Bugzilla: https://bugs.gentoo.org/


.. vim:syn=rst
