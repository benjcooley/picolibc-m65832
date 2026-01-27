#
# SPDX-License-Identifier: BSD-3-Clause
#
# Copyright © 2026 M65832 Project
#
# M65832 machine-specific sources

srcs_machine = [
    'setjmp.c',
]

has_ieeefp_funcs = false

foreach params : targets
  target = params['name']
  target_c_args = params['c_args']
  set_variable('lib_machine' + target,
    static_library('machine' + target,
      srcs_machine,
      pic: false,
      include_directories: inc,
      c_args: target_c_args + c_args + arg_fnobuiltin))
endforeach
