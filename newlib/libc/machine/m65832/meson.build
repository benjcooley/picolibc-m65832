#
# SPDX-License-Identifier: BSD-3-Clause
#
# Copyright © 2024 M65832 Project
#
# M65832 machine-specific libc sources
#

srcs_machine = [
    'm65832_iob.c',
]

foreach target : targets
    value = get_variable('target_' + target)
    set_variable('lib_machine' + target,
        static_library('machine' + target,
            srcs_machine,
            pic: false,
            include_directories: inc,
            c_args: value[1] + c_args))
endforeach
